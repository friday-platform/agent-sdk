# WASM Constraints, Casing Rules, and Common Mistakes

## Table of Contents

- [WASM Sandbox Constraints](#wasm-sandbox-constraints)
- [Casing Rules](#casing-rules)
- [Build Pipeline](#build-pipeline)
- [Common Mistakes and Fixes](#common-mistakes-and-fixes)
- [One Agent Per Module](#one-agent-per-module)
- [Streaming LLM Responses](#streaming-llm-responses)

---

## WASM Sandbox Constraints

### What's available

The Python standard library works. If a module is pure stdlib (`json`, `re`,
`dataclasses`, `collections`, `datetime`, `uuid`, `base64`, `urllib.parse`,
etc.), it's safe to use.

### What's blocked

Anything that touches the OS, network, or has native C/Rust extensions:

| Blocked                               | Why                        | Alternative                           |
| ------------------------------------- | -------------------------- | ------------------------------------- |
| `requests`, `httpx`, `urllib.request` | Network access blocked     | `ctx.http.fetch()`                    |
| `anthropic`, `openai`                 | pydantic-core (Rust C ext) | `ctx.llm.generate()`                  |
| `pydantic`                            | pydantic-core (Rust C ext) | `dataclasses`                         |
| `numpy`, `pandas`, `scipy`            | C extensions               | Process data on host side             |
| `ssl`, `socket`                       | Network primitives         | Host handles TLS                      |
| `subprocess`, `os.system`             | No process spawning        | `ctx.tools.call("bash", ...)` via MCP |
| `threading`, `multiprocessing`        | Single-threaded WASM       | Sequential execution                  |
| `open()`, `pathlib`, `os.path`        | No filesystem              | Data via prompt/HTTP/tools            |
| `sqlite3`                             | Native library             | Use MCP database tools                |
| `PIL/Pillow`                          | C extensions               | Process images via HTTP API           |
| `aiohttp`, `asyncio`                  | No async in WASM yet       | Synchronous SDK calls                 |

### The rule of thumb

If `pip install <package>` downloads a `.whl` with platform-specific tags
(like `cp311-cp311-manylinux`), it has native extensions and won't work.
Pure-Python packages (those with `py3-none-any.whl`) might work if they don't
import blocked modules.

---

## Casing Rules

The SDK spans a Python/JavaScript boundary. Casing conventions differ on each side,
and the bridge layer handles conversion for decorator metadata automatically.

### Your code (Python side)

| Context          | Convention   | Example                                                |
| ---------------- | ------------ | ------------------------------------------------------ |
| Decorator kwargs | `snake_case` | `display_name`, `input_schema`, `use_workspace_skills` |
| Dataclass fields | `snake_case` | `issue_key`, `max_results`                             |
| Function names   | `snake_case` | `_handle_view`, `_build_auth`                          |
| Variable names   | `snake_case` | `api_key`, `response_data`                             |

### Dict values passed to host

| Context               | Convention  | Example                                   |
| --------------------- | ----------- | ----------------------------------------- |
| Environment `linkRef` | `camelCase` | `{"linkRef": {"provider": "..."}}`        |
| MCP transport config  | `camelCase` | `{"type": "stdio", "command": "..."}`     |
| Stream event data     | `camelCase` | `{"toolName": "agent", "content": "..."}` |

### What the bridge converts automatically

The `_bridge.py` module converts decorator metadata to camelCase when serializing
for the host:

- `display_name` → `displayName`
- `use_workspace_skills` → `useWorkspaceSkills`
- `input_schema` → `inputSchema` (after JSON Schema extraction)

You don't need to worry about this conversion — just use snake_case in Python
and the bridge handles it.

---

## Build Pipeline

`atlas agent build` handles the full pipeline:

```
agent.py → componentize-py → agent.wasm → jco transpile → agent-js/ → Zod validation → metadata.json
```

You don't run these tools directly. If a build fails, the error message
includes the phase (`compile`, `transpile`, `validate`, `write`) and details.

---

## Common Mistakes and Fixes

### Missing Agent import

```python
# WRONG — build fails with "no exported Agent class"
from friday_agent_sdk import agent, ok

@agent(id="my-agent", version="1.0.0", description="...")
def execute(prompt, ctx):
    return ok("hello")
```

```python
# CORRECT — Agent import is required even though unused
from friday_agent_sdk import agent, ok
from friday_agent_sdk._bridge import Agent  # noqa: F401

@agent(id="my-agent", version="1.0.0", description="...")
def execute(prompt, ctx):
    return ok("hello")
```

### Returning raw values instead of ok/err

```python
# WRONG — bridge doesn't know how to serialize raw dicts
def execute(prompt, ctx):
    return {"result": "data"}
```

```python
# CORRECT
def execute(prompt, ctx):
    return ok({"result": "data"})
```

### Trying to import blocked packages

```python
# WRONG — fails at build time
import requests
response = requests.get("https://api.example.com")
```

```python
# CORRECT — use host HTTP capability
response = ctx.http.fetch("https://api.example.com")
```

### Using pydantic for schemas

```python
# WRONG — pydantic-core is a Rust C extension
from pydantic import BaseModel

class Config(BaseModel):
    url: str
```

```python
# CORRECT — dataclasses are stdlib
from dataclasses import dataclass

@dataclass
class Config:
    url: str
```

### Not handling None capabilities

```python
# WRONG — ctx.llm could be None
def execute(prompt, ctx):
    result = ctx.llm.generate(messages=[...])  # AttributeError if None
```

```python
# CORRECT — either check or declare in decorator so platform provides it
def execute(prompt, ctx):
    if ctx.llm is None:
        return err("LLM capability not available")
    result = ctx.llm.generate(messages=[...])
```

### Confusing generate_object schema format

```python
# WRONG — generate_object takes a JSON Schema dict, not a dataclass
@dataclass
class Output:
    summary: str

result = ctx.llm.generate_object(messages=[...], schema=Output)
```

```python
# CORRECT — JSON Schema dict
result = ctx.llm.generate_object(
    messages=[...],
    schema={
        "type": "object",
        "properties": {"summary": {"type": "string"}},
        "required": ["summary"],
    },
)
```

Note: `parse_input` takes dataclasses for validation. `generate_object` takes
JSON Schema dicts for LLM constraint. Different tools, different schema formats.

### Using parse_input with non-dataclass

```python
# WRONG — parse_input schema must be a dataclass
class Config:
    url: str

config = parse_input(prompt, Config)  # TypeError
```

```python
# CORRECT
from dataclasses import dataclass

@dataclass
class Config:
    url: str

config = parse_input(prompt, Config)  # works
```

### Multiple agents in one module

```python
# WRONG — raises RuntimeError at import time
@agent(id="agent-a", version="1.0.0", description="...")
def handle_a(prompt, ctx):
    return ok("a")

@agent(id="agent-b", version="1.0.0", description="...")
def handle_b(prompt, ctx):
    return ok("b")
```

One agent per file. Split into separate modules.

---

## One Agent Per Module

The registry enforces a singleton pattern. When `@agent` decorates a function,
it registers with `_registry.py`. A second `@agent` call in the same module
raises `RuntimeError`. This is by design — each `.py` file compiles to one WASM
component.

If you need multiple related agents, create separate files:

```
agents/
  view-agent/agent.py
  search-agent/agent.py
  create-agent/agent.py
```

---

## Streaming LLM Responses

Not yet supported. WASI 0.3 (expected late 2026) will enable streaming.
Currently, `ctx.llm.generate()` blocks until the full response is ready.

For long-running agents, use `ctx.stream.progress()` to emit status updates
between LLM calls so the UI shows activity:

```python
ctx.stream.progress("Analyzing document structure...")
structure = ctx.llm.generate(messages=[...])

ctx.stream.progress("Generating summary...")
summary = ctx.llm.generate(messages=[...])
```
