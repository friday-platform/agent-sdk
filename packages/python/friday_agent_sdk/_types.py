"""Context and data types for agent execution."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


class ToolCallError(Exception):
    """Raised when a host tool call fails."""

    pass


class LlmError(Exception):
    """Raised when a host LLM call fails."""

    pass


class HttpError(Exception):
    """Raised when a host HTTP call fails."""

    pass


@dataclass
class ToolDefinition:
    """A tool available to the agent via MCP."""

    name: str
    description: str
    input_schema: dict


class Tools:
    """Wrapper around NATS capability subjects for tool invocation."""

    def __init__(
        self,
        call_tool: Callable[[str, str], Any],
        list_tools: Callable[[], list],
    ) -> None:
        self._call_tool = call_tool
        self._list_tools = list_tools

    def call(self, name: str, args: dict) -> dict:
        """Call a tool by name. Raises ToolCallError on failure."""
        try:
            result = self._call_tool(name, json.dumps(args))
        except Exception as e:
            raise ToolCallError(str(e)) from e
        return json.loads(result)

    def list(self) -> list[ToolDefinition]:
        """List available tools."""
        raw = self._list_tools()
        return [
            ToolDefinition(
                name=t.name,
                description=t.description,
                input_schema=json.loads(t.input_schema),
            )
            for t in raw
        ]


@dataclass(frozen=True)
class InputArtifactRef:
    """Reference to an artifact supplied through action input."""

    id: str
    type: str = "Artifact"
    summary: str = ""


_MISSING = object()


class AgentInput:
    """Structured input supplied by the Friday runtime.

    `prompt` remains a human-readable enriched string for backwards
    compatibility. `ctx.input` is the structured counterpart: it exposes the
    compact `inputFrom`/config payload without asking agents to scrape JSON out
    of markdown, and provides helpers for explicit artifact dereferencing.
    """

    def __init__(self, raw: dict | None = None, tools: Tools | None = None) -> None:
        self.raw: dict = raw if isinstance(raw, dict) else {}
        self._tools = tools

    @property
    def config(self) -> dict:
        """Input config keyed by `inputFrom` document id and signal fields."""
        config = self.raw.get("config")
        return config if isinstance(config, dict) else {}

    def get(self, name: str | None = None, default: Any = None) -> Any:
        """Return structured input.

        With `name`, lookup prefers `raw["config"][name]` (the usual
        `inputFrom` shape), then falls back to `raw[name]`. Without `name`, the
        full raw runtime input is returned.
        """
        if name is None:
            return self.raw
        if name in self.config:
            return self.config[name]
        return self.raw.get(name, default)

    def require(self, name: str | None = None) -> Any:
        """Like get(), but raise ValueError when the requested input is missing."""
        if name is None:
            if not self.raw:
                raise ValueError("Required action input not found: input")
            return self.raw

        value = self.get(name, _MISSING)
        if value is _MISSING:
            raise ValueError(f"Required action input not found: {name}")
        return value

    def artifact_refs(self, name: str | None = None) -> list[InputArtifactRef]:
        """Return artifact refs found in the selected structured input."""
        target = self.get(name) if name is not None else self.raw
        refs: list[InputArtifactRef] = []
        self._collect_artifact_refs(target, refs)
        return refs

    def artifact_json(self, name: str | None = None) -> Any:
        """Fetch artifact refs through `artifacts_get` and parse JSON contents.

        Returns the parsed payload for a single ref, or a list of parsed payloads
        for multiple refs. This intentionally dereferences inside the worker
        action only; supervisors and persisted output docs can stay compact.
        """
        refs = self.artifact_refs(name)
        if not refs:
            label = name or "input"
            raise ValueError(f"No artifact refs found in action input: {label}")
        if self._tools is None:
            raise ToolCallError("artifacts_get unavailable: ctx.tools is not initialized")

        payloads = [self._read_artifact_json(ref) for ref in refs]
        return payloads[0] if len(payloads) == 1 else payloads

    def _read_artifact_json(self, ref: InputArtifactRef) -> Any:
        if self._tools is None:
            raise ToolCallError("artifacts_get unavailable: ctx.tools is not initialized")
        result = self._tools.call("artifacts_get", {"artifactId": ref.id})
        payload = self._unwrap_tool_payload(result)
        if isinstance(payload, dict) and "contents" in payload:
            contents = payload["contents"]
            if isinstance(contents, str):
                try:
                    return json.loads(contents)
                except json.JSONDecodeError:
                    return contents
        return payload

    @staticmethod
    def _unwrap_tool_payload(result: Any) -> Any:
        if isinstance(result, dict):
            if result.get("isError") is True:
                raise ToolCallError(f"artifacts_get failed: {result}")
            content = result.get("content")
            if isinstance(content, list):
                texts = [item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text"]
                text = "\n".join(part for part in texts if part)
                if text:
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        return text
        return result

    @classmethod
    def _collect_artifact_refs(cls, value: Any, out: list[InputArtifactRef]) -> None:
        if isinstance(value, dict):
            cls._append_ref(value.get("artifactRef"), out)
            raw_refs = value.get("artifactRefs")
            if isinstance(raw_refs, list):
                for raw_ref in raw_refs:
                    cls._append_ref(raw_ref, out)
            for key, child in value.items():
                if key in {"artifactRef", "artifactRefs", "artifactContent"}:
                    continue
                cls._collect_artifact_refs(child, out)
        elif isinstance(value, list):
            for item in value:
                cls._collect_artifact_refs(item, out)

    @staticmethod
    def _append_ref(raw: Any, out: list[InputArtifactRef]) -> None:
        if not isinstance(raw, dict):
            return
        ref_id = raw.get("id") or raw.get("artifactId") or raw.get("artifact_id")
        if not isinstance(ref_id, str) or not ref_id:
            return
        raw_type = raw.get("type")
        ref_type = raw_type if isinstance(raw_type, str) else "Artifact"
        raw_summary = raw.get("summary")
        summary = raw_summary if isinstance(raw_summary, str) else ""
        if any(existing.id == ref_id for existing in out):
            return
        out.append(InputArtifactRef(id=ref_id, type=ref_type, summary=summary))


@dataclass
class LlmResponse:
    """Response from an LLM generation call."""

    text: str | None
    object: dict | None
    model: str
    usage: dict
    finish_reason: str


@dataclass
class HttpResponse:
    """Response from an HTTP fetch call."""

    status: int
    headers: dict[str, str]
    body: str

    def json(self) -> Any:
        """Parse body as JSON."""
        return json.loads(self.body)


class Llm:
    """Wrapper around NATS llm-generate capability subject."""

    def __init__(
        self,
        llm_generate: Callable[[str], str],
        agent_llm_config: dict | None = None,
    ) -> None:
        self._llm_generate = llm_generate
        self._config = agent_llm_config or {}

    def _parse_response(self, raw: str) -> LlmResponse:
        """Parse a JSON response string into an LlmResponse."""
        data = json.loads(raw)
        return LlmResponse(
            text=data.get("text"),
            object=data.get("object"),
            model=data["model"],
            usage=data["usage"],
            finish_reason=data["finish_reason"],
        )

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        provider_options: dict | None = None,
    ) -> LlmResponse:
        """Generate text from an LLM.

        Model resolution: explicit model param > agent llm config > error.
        """
        request: dict = {"messages": messages}
        if model is not None:
            request["model"] = model
        if max_tokens is not None:
            request["max_tokens"] = max_tokens
        if temperature is not None:
            request["temperature"] = temperature
        if provider_options is not None:
            request["provider_options"] = provider_options

        try:
            raw = self._llm_generate(json.dumps(request))
        except Exception as e:
            raise LlmError(str(e)) from e

        return self._parse_response(raw)

    def generate_object(
        self,
        messages: list[dict[str, str]],
        schema: dict,
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        provider_options: dict | None = None,
    ) -> LlmResponse:
        """Generate a structured object matching a JSON Schema.

        Returns LlmResponse with .object populated and .text as None.
        Consistent with generate() — callers access response.object.
        """
        request: dict = {"messages": messages, "output_schema": schema}
        if model is not None:
            request["model"] = model
        if max_tokens is not None:
            request["max_tokens"] = max_tokens
        if temperature is not None:
            request["temperature"] = temperature
        if provider_options is not None:
            request["provider_options"] = provider_options

        try:
            raw = self._llm_generate(json.dumps(request))
        except Exception as e:
            raise LlmError(str(e)) from e

        return self._parse_response(raw)


class Http:
    """Wrapper around NATS http-fetch capability subject."""

    def __init__(self, http_fetch: Callable[[str], str]) -> None:
        self._http_fetch = http_fetch

    def fetch(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: str | None = None,
        timeout_ms: int | None = None,
    ) -> HttpResponse:
        """Make an outbound HTTP request through the host."""
        request: dict = {"url": url, "method": method}
        if headers is not None:
            request["headers"] = headers
        if body is not None:
            request["body"] = body
        if timeout_ms is not None:
            request["timeout_ms"] = timeout_ms

        try:
            raw = self._http_fetch(json.dumps(request))
        except Exception as e:
            raise HttpError(str(e)) from e

        data = json.loads(raw)
        return HttpResponse(
            status=data["status"],
            headers=data.get("headers", {}),
            body=data.get("body", ""),
        )


class StreamEmitter:
    """Publishes stream events directly to the NATS session subject."""

    def __init__(self, stream_emit: Callable[[str, str], None]) -> None:
        self._stream_emit = stream_emit

    def emit(self, event_type: str, data: dict | str) -> None:
        """Emit a raw stream event to the host."""
        payload = json.dumps(data) if isinstance(data, dict) else data
        self._stream_emit(event_type, payload)

    def progress(self, content: str, *, tool_name: str | None = None) -> None:
        """Emit a data-tool-progress event."""
        self.emit(
            "data-tool-progress",
            {"toolName": tool_name or "agent", "content": content},
        )

    def intent(self, content: str) -> None:
        """Emit a data-intent event."""
        self.emit("data-intent", {"content": content})


@dataclass
class SessionData:
    """Session metadata passed from the host."""

    id: str
    workspace_id: str
    user_id: str
    datetime: str


def _uninitialized_llm():
    """Factory for uninitialized LLM stub."""

    def stub(_: str) -> str:
        raise RuntimeError("LLM capability not initialized - this should only happen in tests without proper context setup")

    return Llm(stub)


def _uninitialized_tools():
    """Factory for uninitialized Tools stub."""

    def call_stub(_: str, __: str) -> Any:
        raise RuntimeError(
            "Tools capability not initialized - this should only happen in tests without proper context setup"
        )

    def list_stub() -> list:
        return []

    return Tools(call_stub, list_stub)


def _uninitialized_http():
    """Factory for uninitialized Http stub."""

    def stub(_: str) -> str:
        raise RuntimeError("HTTP capability not initialized - this should only happen in tests without proper context setup")

    return Http(stub)


def _uninitialized_stream():
    """Factory for uninitialized StreamEmitter stub (no-op)."""

    def stub(_: str, __: str) -> None:
        pass

    return StreamEmitter(stub)


def _uninitialized_input():
    """Factory for empty structured input."""
    return AgentInput({}, _uninitialized_tools())


@dataclass
class SkillDefinition:
    """A workspace skill injected at agent invocation time."""

    name: str
    description: str
    instructions: str


@dataclass
class AgentContext:
    """Execution context passed to agent handlers.

    Capability fields (llm, tools, http, stream) are always non-None.
    Defaults are safe stubs that raise if called outside the host environment.
    """

    env: dict[str, str] = field(default_factory=dict)
    config: dict = field(default_factory=dict)
    skills: list[SkillDefinition] = field(default_factory=list)
    session: SessionData | None = None
    output_schema: dict | None = None
    input: AgentInput = field(default_factory=_uninitialized_input)
    tools: Tools = field(default_factory=_uninitialized_tools)
    llm: Llm = field(default_factory=_uninitialized_llm)
    http: Http = field(default_factory=_uninitialized_http)
    stream: StreamEmitter = field(default_factory=_uninitialized_stream)
