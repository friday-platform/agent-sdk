# How Friday Agents Work

Understanding the architecture behind Python agents in Friday.

## Overview

Friday runs your Python agent as a native subprocess. When the platform needs to execute your agent, it spawns `python3 agent.py`, sends the prompt and context over an internal message broker, and collects the result. You don't manage the process or the broker — the SDK handles all the wire protocol. You write plain Python using the `@agent` decorator and `ctx` capabilities, and the SDK bridge connects, receives the execute request, builds the context, calls your handler, and returns the result.

## What You Write

Python code using the `@agent` decorator and `ctx` capabilities, ending with a `run()` call:

```python
from friday_agent_sdk import agent, ok, run

@agent(id="my-agent", version="1.0.0", description="Does something")
def execute(prompt, ctx):
    result = ctx.llm.generate(messages, model="anthropic:claude-sonnet-4-6")
    return ok({"output": result.text})

if __name__ == "__main__":
    run()
```

The `run()` call at the bottom is the entry point. When Friday spawns your agent, it sets environment variables that `run()` detects:

- **Registration mode** — publish metadata to the daemon, then exit
- **Execution mode** — subscribe for a request, handle it, respond, then exit

## What Happens When You Register

When you run `atlas agent register ./my-agent`:

1. **Validate** — The daemon spawns your agent in registration mode. It publishes metadata (id, version, description, etc.) and exits.
2. **Store** — The daemon copies your source directory to `~/.friday/local/agents/{id}@{version}/` and writes a `metadata.json` sidecar.
3. **Reload** — The agent registry picks up the new agent.

No compilation, no transpilation. The source code is stored as-is.

## What Happens At Execution

When Friday needs to run your agent:

1. **Spawn** — `python3 agent.py` is launched with execution environment variables
2. **Signal ready** — The SDK connects to the daemon's message broker and signals it's ready to receive a request
3. **Receive** — The daemon sends the prompt and context as JSON
4. **Handle** — The SDK builds `AgentContext` from the raw dict and calls your `@agent` function
5. **Respond** — Your `ok()`/`err()` result is serialized and sent back
6. **Exit** — The agent process terminates (each execution is a fresh process)

## Host Capabilities

All I/O routes through Friday so the platform can manage credentials, rate limits, audit logging, and provider routing centrally:

| Capability   | What It Does                                          | Why Through Friday                                           |
| ------------ | ----------------------------------------------------- | ------------------------------------------------------------ |
| `ctx.llm`    | Routes LLM calls through Friday's provider registry   | Host manages API keys, rate limits, model routing            |
| `ctx.http`   | Makes HTTP requests via Friday's fetch layer          | Host handles TLS termination, audit logging, response limits |
| `ctx.tools`  | Calls MCP tools running in the host                   | MCP servers run outside the agent process                    |
| `ctx.stream` | Emits progress updates to the Friday UI               | No direct UI access from subprocess                          |
| `ctx.env`    | Reads environment variables you configure in `@agent` | Host injects vars; agent has no direct env access            |

## The Contract

Friday and your agent communicate via a simple JSON protocol over an internal message broker:

- **Agent publishes** metadata during registration
- **Agent signals ready** before each execution
- **Daemon sends** `{prompt, context}` JSON
- **Agent responds** with `{tag: "ok" | "err", val: string}` envelope
- **Agent publishes** stream events (progress, intents) during execution
- **Daemon handles** LLM calls, HTTP requests, and MCP tool calls on behalf of the agent

Data crosses as JSON. Schemas evolve without interface version bumps.

## SDK is a Runtime Dependency

The `friday-agent-sdk` package is a **runtime dependency** installed into your Python environment. At execution time, your agent imports it like any other Python package. You can `pip install` additional pure-Python packages into the same environment.

This means:

- You **can** `pip install` packages into the agent environment
- Native C extensions work (NumPy, Pydantic, etc.) if the environment has them
- All I/O still goes through host capabilities for audit and credential management
- The agent is a normal Python process — no sandbox

## Limitations

- **No streaming LLM responses** — `ctx.llm.generate()` blocks until the full response is ready
- **One agent per file** — Each `.py` registers exactly one `@agent`
- **5MB HTTP response limit** — Matches Friday's platform webfetch limit
- **Spawn-per-call** — Each execution starts a fresh process; keep startup lightweight

## Iteration Workflow

```bash
vim agent.py
atlas agent register ./my-agent
atlas agent exec my-agent -i "test input"
```

Or test directly against the playground:

```bash
curl -s -X POST http://localhost:5200/api/agents/my-agent/run \
  -H 'Content-Type: application/json' \
  -d '{"input": "test prompt"}'
```

Friday resolves agent IDs to the latest semver version automatically. Re-register with a bumped version (`1.0.1`) to keep old iterations available.

## See Also

- [Your First Friday Agent](../tutorial/your-first-agent.md) — Step-by-step walkthrough
- [Agent Decorator](../reference/agent-decorator.md) — Metadata and registration parameters
