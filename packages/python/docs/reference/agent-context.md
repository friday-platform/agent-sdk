# AgentContext

Execution context passed to agent handlers, providing access to environment, capabilities, and metadata.

## Definition

```python
@dataclass
class AgentContext:
    env: dict[str, str] = field(default_factory=dict)
    config: dict = field(default_factory=dict)
    session: SessionData | None = None
    output_schema: dict | None = None
    tools: Tools | None = None
    llm: Llm | None = None
    http: Http | None = None
    stream: StreamEmitter | None = None
```

## Fields

### `env`

- **Type:** `dict[str, str]`
- **Description:** Environment variables configured via the `@agent` decorator's `environment` field.

```python
api_key = ctx.env["ANTHROPIC_API_KEY"]  # Raises KeyError if not set
debug = ctx.env.get("DEBUG", "false")   # Safe access with default
```

Populated from Friday's environment matching `environment.required` and `environment.optional` configuration.

### `config`

- **Type:** `dict`
- **Description:** Agent-specific configuration and workspace context.

May include:

- `platformUrl` — Friday API base URL
- `skills` — List of workspace skills for the session
- `workDir` — Existing workspace directory (if FSM set one up)
- Custom fields passed by the orchestrator

```python
platform_url = ctx.config.get("platformUrl", "http://localhost:8080")
skills = ctx.config.get("skills", [])
```

### `session`

- **Type:** `SessionData | None`
- **Description:** Session metadata when running within a Friday session.

```python
@dataclass
class SessionData:
    id: str            # Session identifier
    workspace_id: str  # Workspace identifier
    user_id: str       # User identifier
    datetime: str      # ISO format timestamp
```

May be `None` in test contexts or standalone execution.

### `output_schema`

- **Type:** `dict | None`
- **Description:** JSON Schema for structured output, if specified by the caller.

```python
if ctx.output_schema:
    # Use structured generation
    result = ctx.llm.generate_object(..., schema=ctx.output_schema)
else:
    # Standard text generation
    result = ctx.llm.generate(...)
```

### `tools`

- **Type:** `Tools | None`
- **Description:** MCP tool capability wrapper. Available when MCP servers are configured.

Methods:

- `ctx.tools.list()` → `list[ToolDefinition]`
- `ctx.tools.call(name, args)` → `dict`

See [ctx.tools](tools-capability.md).

### `llm`

- **Type:** `Llm | None`
- **Description:** LLM capability wrapper for generation calls.

Methods:

- `ctx.llm.generate(messages, model, ...)` → `LlmResponse`
- `ctx.llm.generate_object(messages, schema, ...)` → `LlmResponse`

See [ctx.llm](llm-capability.md).

### `http`

- **Type:** `Http | None`
- **Description:** HTTP capability wrapper for outbound requests.

Methods:

- `ctx.http.fetch(url, method, headers, body, timeout_ms)` → `HttpResponse`

See [ctx.http](http-capability.md).

### `stream`

- **Type:** `StreamEmitter | None`
- **Description:** Stream capability for progress emission.

Methods:

- `ctx.stream.progress(content, tool_name)`
- `ctx.stream.intent(content)`
- `ctx.stream.emit(event_type, data)`

See [ctx.stream](stream-capability.md).

## Availability Guarantees

| Field           | Guaranteed | Notes                                   |
| --------------- | ---------- | --------------------------------------- |
| `env`           | Yes        | Empty dict if no environment configured |
| `config`        | Yes        | Empty dict if no config provided        |
| `session`       | No         | May be None outside Friday sessions     |
| `output_schema` | No         | Only when caller specifies schema       |
| `tools`         | No         | Only when MCP servers configured        |
| `llm`           | No         | Only when host provides LLM capability  |
| `http`          | No         | Only when host provides HTTP capability |
| `stream`        | No         | May be None in test contexts            |

## Defensive Programming

```python
from friday_agent_sdk import agent, ok

@agent(id="safe", version="1.0.0", description="Handles missing capabilities")
def execute(prompt, ctx):
    # Safe access with fallbacks
    api_key = ctx.env.get("OPTIONAL_KEY")  # Returns None if missing

    # Required access with check
    if "REQUIRED_KEY" not in ctx.env:
        return err("REQUIRED_KEY not set. Connect in Friday Link.")

    # Capability checks
    if ctx.llm is None:
        return err("LLM capability not available")

    if ctx.output_schema:
        # Structured path
        result = ctx.llm.generate_object(...)
    else:
        # Standard path
        result = ctx.llm.generate(...)

    # Safe progress emission
    if ctx.stream:
        ctx.stream.progress("Working...")

    return ok({"result": result.text})
```

## Context Round-Trip

All context fields survive the host-to-WASM-to-host round trip:

1. Friday serialises context as JSON
2. JSON passes to WASM `execute(prompt, context)`
3. SDK bridge deserialises to `AgentContext` dataclass
4. Your code uses the context
5. Result serialises back to host

The `context-inspector` example agent demonstrates all fields survive this round-trip correctly.

## See Also

- [ctx.llm](llm-capability.md) — LLM generation
- [ctx.http](http-capability.md) — HTTP requests
- [ctx.tools](tools-capability.md) — MCP tool calls
- [ctx.stream](stream-capability.md) — Progress streaming
- [Result types](result-types.md) — ok() and err() return values
