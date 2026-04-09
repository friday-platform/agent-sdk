---
name: writing-friday-python-agents
description: >
  Write Python agents for the Friday platform using the friday-agent-sdk.
  Covers the @agent decorator, AgentContext capabilities (ctx.llm, ctx.http,
  ctx.tools, ctx.stream), structured input parsing, result types, WASM sandbox
  constraints, and getting agents into Friday. Use this skill whenever writing,
  editing, debugging, or reviewing a Friday Python agent — including when you
  see imports from friday_agent_sdk, when working in an agents/ directory with
  agent.py files, when the user mentions "Friday agent", "custom agent",
  "Python agent", or "WASM agent", or when creating any agent that will run on
  the Friday platform. Even if the user doesn't explicitly mention the SDK,
  load this skill if the context suggests they're building something that will
  run as a Friday agent.
---

# Writing Friday Python Agents

Friday agents are single-file Python modules that compile to WebAssembly and run
in a sandboxed environment. The SDK is a compile-time dependency — it gets baked
into the WASM binary. There are no runtime dependencies.

The mental model: your Python code runs inside a WASM sandbox with no filesystem,
no network, no native extensions. All I/O happens through **host capabilities**
the platform provides — LLM generation, HTTP requests, MCP tools, and progress
streaming. You declare what you need in the `@agent` decorator, and the platform
wires it up at execution time via `AgentContext`.

## Every Agent Looks Like This

```python
from friday_agent_sdk import agent, ok, AgentContext
from friday_agent_sdk._bridge import Agent  # noqa: F401 — required for componentize-py

@agent(
    id="my-agent",
    version="1.0.0",
    description="What this agent does — the planner reads this to decide when to invoke it",
)
def execute(prompt: str, ctx: AgentContext):
    # Your logic here
    return ok({"result": "data"})
```

Three things are non-negotiable:

1. **The `Agent` import** — `from friday_agent_sdk._bridge import Agent` must be
   present even though you never reference `Agent` directly. componentize-py
   discovers this class to generate the WASM exports. Without it, the build fails.
2. **The `@agent` decorator** with at least `id`, `version`, `description`.
3. **Return `ok()` or `err()`** — never return raw dicts/strings.

## Capabilities Quick Reference

All capabilities live on `AgentContext` and may be `None` if not wired up.
Check before using, or declare what you need in the decorator so the platform
provides it.

| Capability  | Access        | What it does                                              |
| ----------- | ------------- | --------------------------------------------------------- |
| LLM         | `ctx.llm`     | Generate text or structured objects via host LLM registry |
| HTTP        | `ctx.http`    | Make outbound HTTP requests (TLS handled by host)         |
| MCP Tools   | `ctx.tools`   | Call MCP server tools (GitHub, Jira, databases, etc.)     |
| Streaming   | `ctx.stream`  | Emit progress/intent events to the UI                     |
| Environment | `ctx.env`     | Read environment variables (API keys, config)             |
| Config      | `ctx.config`  | Agent-specific configuration from workspace               |
| Session     | `ctx.session` | Session metadata (id, workspace_id, user_id, datetime)    |

### ctx.llm — LLM Generation

```python
# Text generation
response = ctx.llm.generate(
    messages=[{"role": "user", "content": "Summarize this document"}],
    model="anthropic:claude-sonnet-4-6",  # fully qualified
)
print(response.text)  # str

# Structured output — returns response.object (dict), response.text is None
response = ctx.llm.generate_object(
    messages=[{"role": "user", "content": "Extract key facts"}],
    schema={"type": "object", "properties": {"facts": {"type": "array", "items": {"type": "string"}}}},
    model="anthropic:claude-haiku-4-5",
)
print(response.object)  # dict matching schema
```

Pass a fully qualified model like `anthropic:claude-sonnet-4-6`, or set defaults
in the `llm` decorator param and omit the per-call `model`.

Optional params: `max_tokens`, `temperature`, `provider_options` (dict).

### ctx.http — Outbound HTTP

```python
response = ctx.http.fetch(
    "https://api.example.com/data",
    method="POST",
    headers={"Authorization": f"Bearer {ctx.env['API_KEY']}"},
    body='{"query": "test"}',
    timeout_ms=30000,
)
data = response.json()  # convenience method
# response.status (int), response.headers (dict), response.body (str)
```

The host handles TLS — the sandbox can't import `ssl`. 5MB response body limit.
Note: HTTP status errors (4xx, 5xx) don't raise — check `response.status` manually.

### ctx.tools — MCP Tools

Declare MCP servers in the decorator, then call tools at runtime:

```python
@agent(
    id="my-agent", version="1.0.0", description="...",
    mcp={
        "github": {
            "transport": {
                "type": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
                "env": {"GITHUB_TOKEN": "{{env.GITHUB_TOKEN}}"}
            }
        }
    },
)
def execute(prompt: str, ctx: AgentContext):
    available = ctx.tools.list()  # list[ToolDefinition] — name, description, input_schema
    result = ctx.tools.call("create_issue", {"title": "Bug", "repo": "owner/repo"})
```

`{{env.VARIABLE}}` in MCP config references agent environment variables.
Currently only `stdio` transport is supported.

### ctx.stream — Progress Events

```python
ctx.stream.progress("Analyzing document...", tool_name="analysis")
ctx.stream.intent("Switching to code review phase")
ctx.stream.emit("custom-event", {"key": "value"})  # raw event
```

Emit progress _before_ expensive operations so the UI shows what's happening.
Note: `ctx.stream` may be `None` — check before calling.

## Structured Input Handling

Friday sends "enriched prompts" — markdown with embedded JSON containing task
details, signal data, and context. Code agents need to extract structured data
from these.

### parse_input — Simple extraction

```python
from friday_agent_sdk import parse_input

# Raw dict extraction
data = parse_input(prompt)  # returns dict

# Typed extraction with a dataclass schema
@dataclass
class TaskConfig:
    url: str
    max_retries: int = 3

config = parse_input(prompt, TaskConfig)  # returns TaskConfig instance
```

Extraction strategy (3-level fallback):

1. Balanced-brace JSON scan (handles nested objects)
2. Code-fenced ` ```json ` blocks
3. Entire prompt as JSON

Unknown keys are automatically filtered when using a dataclass schema.

### parse_operation — Discriminated dispatch

For agents that handle multiple operation types:

```python
from friday_agent_sdk import parse_operation
from dataclasses import dataclass

@dataclass
class ViewConfig:
    operation: str
    item_id: str

@dataclass
class SearchConfig:
    operation: str
    query: str
    max_results: int = 50

OPERATIONS = {
    "view": ViewConfig,
    "search": SearchConfig,
}

config = parse_operation(prompt, OPERATIONS)  # dispatches on "operation" field

match config.operation:
    case "view": return handle_view(config, ctx)
    case "search": return handle_search(config, ctx)
```

## Result Types

Always return `ok()` or `err()`. Never return raw values.

```python
from friday_agent_sdk import ok, err

# Simple success
return ok({"status": "done", "count": 42})

# Error
return err("Jira API returned 403: insufficient permissions")
```

`ok()` accepts any JSON-serializable data: dicts, lists, strings, dataclass
instances (auto-converted via `dataclasses.asdict`).

## The WASM Sandbox — What You Cannot Do

This is the single most important thing to internalize. The agent runs inside a
WebAssembly sandbox with only the Python standard library available.

**Blocked — will fail at build time or runtime:**

- `import requests`, `import httpx` — use `ctx.http.fetch()` instead
- `import pydantic` — use `dataclasses` instead (pydantic-core is a Rust C extension)
- `import numpy`, `import pandas` — native C extensions, blocked
- `import ssl`, `import socket` — networking handled by host
- `import anthropic`, `import openai` — use `ctx.llm.generate()` instead
- Any package with native/C extensions
- File system access (`open()`, `pathlib`) — no filesystem in sandbox
- Subprocess/threading — single-threaded WASM execution

**Available — Python standard library works:**

- `json`, `re`, `base64`, `urllib.parse`, `dataclasses`
- `collections`, `itertools`, `functools`, `typing`
- `math`, `datetime`, `uuid`, `hashlib`
- Pure-Python third-party packages (rare — most useful ones have native deps)

When in doubt: if a package appears in PyPI with C extensions or Rust bindings,
it won't work. Stick to stdlib + the SDK's host capabilities.

## Getting Agents Into Friday

### Docker Compose (recommended for development)

Place your agent in the `agents/` directory:

```
agents/
  my-agent/
    agent.py
```

Docker Compose watches this directory. Restart the platform to pick up changes:

```bash
docker compose restart platform
```

### CLI

```bash
# Build an agent
atlas agent build ./agents/my-agent/agent.py

# Reload the agent registry (after editing)
curl -X POST http://localhost:8080/api/agents/reload

# Test directly
atlas agent exec my-agent -i "test prompt"
```

### Workspace Configuration

Register your agent in `workspace.yml`:

```yaml
agents:
  - id: my-agent
    type: user
```

## Casing Convention

This is a subtle but real source of bugs:

- **Decorator kwargs**: `snake_case` (Pythonic) — `display_name`, `input_schema`, `use_workspace_skills`
- **Dict values inside decorator**: `camelCase` (matches host Zod schemas) — `linkRef`, `displayName` inside environment dicts
- **MCP config keys**: `camelCase` in transport config
- **Result data**: your choice, but `snake_case` is conventional for Python agents

The bridge layer (`_bridge.py`) handles converting decorator metadata to
camelCase for the host automatically. You don't need to worry about the boundary
— just follow the convention above.

## References

For deeper dives, read these reference files:

- **`references/api.md`** — Complete API reference: every decorator param, every
  context field, every method signature and return type
- **`references/examples.md`** — Annotated example agents from simple (echo) to
  complex (Jira multi-operation, GitHub PR operations)
- **`references/constraints.md`** — Full list of WASM constraints, casing rules,
  build pipeline details, and common mistakes with fixes
