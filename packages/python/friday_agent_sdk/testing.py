"""Test helpers for unit-testing Friday agents.

The `AgentContext` capability fields (`ctx.llm`, `ctx.http`, `ctx.tools`,
`ctx.stream`) are typed as protocols so any object implementing the right
methods can be substituted in tests. This module provides ready-made fakes
plus a `make_test_context()` constructor that wires sensible defaults.

Example:

    from friday_agent_sdk import LlmResponse
    from friday_agent_sdk.testing import FakeLlm, make_test_context

    fake_llm = FakeLlm(
        responses=[
            LlmResponse(
                text="hello there",
                object=None,
                model="fake",
                usage={},
                finish_reason="stop",
            )
        ]
    )
    ctx = make_test_context(env={"API_KEY": "x"}, llm=fake_llm)

    result = my_agent_handler("hi", ctx)
    assert fake_llm.calls[0]["messages"] == [{"role": "user", "content": "hi"}]
"""

from collections.abc import Callable
from typing import Any

from friday_agent_sdk._types import (
    AgentContext,
    HttpProtocol,
    HttpResponse,
    LlmProtocol,
    LlmResponse,
    SessionData,
    SkillDefinition,
    StreamProtocol,
    ToolCallError,
    ToolDefinition,
    ToolsProtocol,
)

__all__ = [
    "FakeHttp",
    "FakeLlm",
    "FakeStream",
    "FakeTools",
    "make_test_context",
]


def _empty_llm_response() -> LlmResponse:
    return LlmResponse(
        text="",
        object=None,
        model="fake",
        usage={},
        finish_reason="stop",
    )


def _empty_http_response() -> HttpResponse:
    return HttpResponse(status=200, headers={}, body="")


class FakeLlm:
    """Test double for `LlmProtocol`.

    Default behaviour returns an empty success `LlmResponse` for every call.
    Override by passing one of:

    - `responses=[LlmResponse(...), ...]` — FIFO queue of canned responses.
      Falls back to the empty default once exhausted.
    - `on_generate=lambda **kwargs: LlmResponse(...)` — custom callable
      invoked for every `generate` and `generate_object` call.

    All calls are appended to `self.calls` for assertion.
    """

    def __init__(
        self,
        responses: list[LlmResponse] | None = None,
        *,
        on_generate: Callable[..., LlmResponse] | None = None,
    ) -> None:
        self._responses: list[LlmResponse] = list(responses or [])
        self._on_generate = on_generate
        self.calls: list[dict[str, Any]] = []

    def _next(self, **kwargs: Any) -> LlmResponse:
        if self._on_generate is not None:
            return self._on_generate(**kwargs)
        if self._responses:
            return self._responses.pop(0)
        return _empty_llm_response()

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        provider_options: dict | None = None,
    ) -> LlmResponse:
        self.calls.append(
            {
                "method": "generate",
                "messages": messages,
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "provider_options": provider_options,
            }
        )
        return self._next(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            provider_options=provider_options,
        )

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
        self.calls.append(
            {
                "method": "generate_object",
                "messages": messages,
                "schema": schema,
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "provider_options": provider_options,
            }
        )
        return self._next(
            messages=messages,
            schema=schema,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            provider_options=provider_options,
        )


class FakeHttp:
    """Test double for `HttpProtocol`.

    Default behaviour returns `HttpResponse(status=200, headers={}, body="")`
    for every call. Override with:

    - `responses=[HttpResponse(...), ...]` — FIFO queue.
    - `on_fetch=lambda url, **kwargs: HttpResponse(...)` — custom callable.

    All calls are appended to `self.calls`.
    """

    def __init__(
        self,
        responses: list[HttpResponse] | None = None,
        *,
        on_fetch: Callable[..., HttpResponse] | None = None,
    ) -> None:
        self._responses: list[HttpResponse] = list(responses or [])
        self._on_fetch = on_fetch
        self.calls: list[dict[str, Any]] = []

    def fetch(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: str | None = None,
        timeout_ms: int | None = None,
    ) -> HttpResponse:
        self.calls.append(
            {
                "url": url,
                "method": method,
                "headers": headers,
                "body": body,
                "timeout_ms": timeout_ms,
            }
        )
        if self._on_fetch is not None:
            return self._on_fetch(
                url,
                method=method,
                headers=headers,
                body=body,
                timeout_ms=timeout_ms,
            )
        if self._responses:
            return self._responses.pop(0)
        return _empty_http_response()


class FakeTools:
    """Test double for `ToolsProtocol`.

    `list()` returns the `tools` argument verbatim. `call(name, args)`
    dispatches via `handlers[name]`; if no handler is registered the call
    raises `ToolCallError` with a clear message — surfacing missing test
    setup loudly is preferred over silent empty returns.

    All calls are appended to `self.calls` as `(name, args)` tuples.
    """

    def __init__(
        self,
        *,
        tools: list[ToolDefinition] | None = None,
        handlers: dict[str, Callable[[dict], dict]] | None = None,
    ) -> None:
        self._tools: list[ToolDefinition] = list(tools or [])
        self._handlers: dict[str, Callable[[dict], dict]] = dict(handlers or {})
        self.calls: list[tuple[str, dict]] = []

    def call(self, name: str, args: dict) -> dict:
        self.calls.append((name, args))
        handler = self._handlers.get(name)
        if handler is None:
            raise ToolCallError(
                f"FakeTools: no handler registered for tool {name!r}. Pass handlers={{...}} when constructing FakeTools()."
            )
        return handler(args)

    def list(self) -> list[ToolDefinition]:
        return list(self._tools)


class FakeStream:
    """Test double for `StreamProtocol`. Records every emitted event into
    `self.events` as `(event_type, data)` tuples. Never raises.
    """

    def __init__(self) -> None:
        self.events: list[tuple[str, dict | str]] = []

    def emit(self, event_type: str, data: dict | str) -> None:
        self.events.append((event_type, data))

    def progress(self, content: str, *, tool_name: str | None = None) -> None:
        self.emit(
            "data-tool-progress",
            {"toolName": tool_name or "agent", "content": content},
        )

    def intent(self, content: str) -> None:
        self.emit("data-intent", {"content": content})


def make_test_context(
    *,
    env: dict[str, str] | None = None,
    config: dict | None = None,
    skills: list[SkillDefinition] | None = None,
    session: SessionData | None = None,
    output_schema: dict | None = None,
    llm: LlmProtocol | None = None,
    http: HttpProtocol | None = None,
    tools: ToolsProtocol | None = None,
    stream: StreamProtocol | None = None,
) -> AgentContext:
    """Construct an `AgentContext` for unit-testing agent handlers.

    Every capability you don't override gets a default `Fake*` instance from
    this module — no NATS, no daemon required. Pass your own protocol
    implementation (or a pre-configured `Fake*`) to control behaviour for
    a specific capability.
    """
    return AgentContext(
        env=env if env is not None else {},
        config=config if config is not None else {},
        skills=skills if skills is not None else [],
        session=session,
        output_schema=output_schema,
        llm=llm if llm is not None else FakeLlm(),
        http=http if http is not None else FakeHttp(),
        tools=tools if tools is not None else FakeTools(),
        stream=stream if stream is not None else FakeStream(),
    )
