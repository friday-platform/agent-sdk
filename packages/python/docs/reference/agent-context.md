# AgentContext

Execution context for agent handlers. Provides environment, capabilities, and metadata.

## Definition

```python
@dataclass
class AgentContext:
    env: dict[str, str] = field(default_factory=dict)
    config: dict = field(default_factory=dict)
    session: SessionData | None = None
    output_schema: dict | None = None
    tools: Tools = field(default_factory=_uninitialized_tools)
    llm: Llm = field(default_factory=_uninitialized_llm)
    http: Http = field(default_factory=_uninitialized_http)
    stream: StreamEmitter = field(default_factory=_uninitialized_stream)
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

- **Type:** `Tools`
- **Description:** MCP tool capability wrapper. Always initialized.

Methods:

- `ctx.tools.list()` → `list[ToolDefinition]`
- `ctx.tools.call(name, args)` → `dict`

See [ctx.tools](tools-capability.md).

### `llm`

- **Type:** `Llm`
- **Description:** LLM capability wrapper for generation calls. Always initialized.

Methods:

- `ctx.llm.generate(messages, model, ...)` → `LlmResponse`
- `ctx.llm.generate_object(messages, schema, ...)` → `LlmResponse`

See [ctx.llm](llm-capability.md).

### `http`

- **Type:** `Http`
- **Description:** HTTP capability wrapper for outbound requests. Always initialized.

Methods:

- `ctx.http.fetch(url, method, headers, body, timeout_ms)` → `HttpResponse`

See [ctx.http](http-capability.md).

### `stream`

- **Type:** `StreamEmitter`
- **Description:** Stream capability for progress emission. Always initialized.

Methods:

- `ctx.stream.progress(content, tool_name)`
- `ctx.stream.intent(content)`
- `ctx.stream.emit(event_type, data)`

See [ctx.stream](stream-capability.md).

## Availability guarantees

| Field           | Guaranteed | Notes                                   |
| --------------- | ---------- | --------------------------------------- |
| `env`           | Yes        | Empty dict if no environment configured |
| `config`        | Yes        | Empty dict if no config provided        |
| `session`       | No         | May be None outside Friday sessions     |
| `output_schema` | No         | Only when caller specifies schema       |
| `tools`         | Yes        | Always initialized (stub in tests)      |
| `llm`           | Yes        | Always initialized (stub in tests)      |
| `http`          | Yes        | Always initialized (stub in tests)      |
| `stream`        | Yes        | Always initialized (stub in tests)      |

## Defensive programming

```python
from friday_agent_sdk import agent, ok, err

@agent(id="safe", version="1.0.0", description="Handles edge cases")
def execute(prompt, ctx):
    # Safe access with fallbacks
    api_key = ctx.env.get("OPTIONAL_KEY")  # Returns None if missing

    # Required access with check
    if "REQUIRED_KEY" not in ctx.env:
        return err("REQUIRED_KEY not set. Connect in Friday Link.")

    # Capabilities are always present; errors come from the host
    try:
        if ctx.output_schema:
            result = ctx.llm.generate_object(..., schema=ctx.output_schema)
        else:
            result = ctx.llm.generate(...)
    except Exception as e:
        return err(f"LLM call failed: {e}")

    ctx.stream.progress("Working...")

    return ok({"result": result.text})
```

## Context round-trip

All context fields survive the host-to-agent round trip:

1. Friday serialises context as JSON
2. JSON is sent to the agent process
3. SDK deserialises to `AgentContext` dataclass
4. Your code uses the context
5. Result serialises back to host

The `context-inspector` example agent demonstrates all fields survive this round-trip correctly.

## See also

- [ctx.llm](llm-capability.md) — LLM generation
- [ctx.http](http-capability.md) — HTTP requests
- [ctx.tools](tools-capability.md) — MCP tool calls
- [ctx.stream](stream-capability.md) — Progress streaming
- [Result types](result-types.md) — ok() and err() return values
