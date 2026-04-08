# How Friday Agents Work

Understanding the architecture behind Python agents in Friday's WebAssembly sandbox.

## Overview

Friday runs your Python agent in a WebAssembly (WASM) sandbox. Your code compiles to a portable WASM component, which Friday loads and executes. The sandbox provides security and isolation: your agent cannot access the filesystem, network, or environment directly. Instead, Friday provides **host capabilities** — platform functions your agent calls for I/O operations.

## What You Write

Python code using the `@agent` decorator and `ctx` capabilities:

```python
from friday_agent_sdk import agent, ok

@agent(id="my-agent", version="1.0.0", description="Does something")
def execute(prompt, ctx):
    result = ctx.llm.generate(messages, model="anthropic:claude-sonnet-4-6")
    return ok({"output": result.text})
```

## What Happens When You Build

When you run `atlas agent build ./agent.py`:

1. **Compile** — `componentize-py` bundles your Python with a CPython interpreter into a `.wasm` file
2. **Transpile** — `jco` converts the WASM to a JavaScript module Friday can load
3. **Validate** — Friday checks your `@agent` metadata against its schema
4. **Store** — Files written to Friday's agent directory, discoverable via the API

All of this happens inside the Friday daemon's Docker container. You do not need `componentize-py` or `jco` installed locally.

## Host Capabilities

Your agent runs in an isolated sandbox. To do anything useful, it calls through Friday:

| Capability   | What It Does                                          | Why Not Direct                                                       |
| ------------ | ----------------------------------------------------- | -------------------------------------------------------------------- |
| `ctx.llm`    | Routes LLM calls through Friday's provider registry   | `anthropic`/`openai` packages need native extensions blocked by WASM |
| `ctx.http`   | Makes HTTP requests via Friday's fetch layer          | Python `ssl` module unavailable in WASM                              |
| `ctx.tools`  | Calls MCP tools running in the host                   | MCP servers run outside the sandbox                                  |
| `ctx.stream` | Emits progress updates to the Friday UI               | No direct UI access from sandbox                                     |
| `ctx.env`    | Reads environment variables you configure in `@agent` | No host environment access                                           |

## The Contract

Friday and your agent communicate via a WIT interface. Key points:

- Your agent **exports** `get-metadata()` and `execute()` — the `@agent` decorator handles this
- Friday **imports** capabilities your agent can call — accessed via `ctx`
- Data crosses as JSON strings — schemas evolve without interface version bumps

The complete contract is in [`packages/wit/agent.wit`](../../../../packages/wit/agent.wit).

## SDK is Compile-Time Only

The `friday-agent-sdk` package is a **compile-time dependency only**. It is baked into your `.wasm` file by `componentize-py`. At runtime, your agent runs in a pure Python environment with zero external dependencies.

This means:

- You cannot `pip install` packages into the sandbox
- Only Python standard library is available
- All I/O goes through host capabilities

## Limitations

- **No native extensions** — NumPy, Pydantic, etc. cannot compile to WASM
- **No streaming LLM responses** — Requires WASI 0.3 (expected late 2026)
- **One agent per file** — Each `.py` builds to one WASM component
- **5MB HTTP response limit** — Matches Friday's platform limits

## Iteration Workflow

With the Friday CLI:

```bash
vim agent.py
atlas agent build ./agent.py
atlas agent exec my-agent -i "test input"
```

With Docker Compose, place your source in `agents/` and restart:

```bash
vim agents/my-agent/agent.py
docker compose restart platform
atlas agent exec my-agent -i "test input" --url http://localhost:15200
```

The daemon rebuilds every agent in `agents/` on startup.

Friday resolves agent IDs to the latest semver version automatically. Rebuild with a bumped version (`1.0.1`) to keep old iterations available.

## See Also

- [Your First Friday Agent](../tutorial/your-first-agent.md) — Step-by-step walkthrough
- [WIT contract](../../../../packages/wit/agent.wit) — Complete interface specification
- [componentize-py](https://github.com/bytecodealliance/componentize-py) — Python-to-WASM compiler
