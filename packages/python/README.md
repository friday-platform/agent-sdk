# Friday Agent SDK for Python

Write AI agents in Python that run inside Friday's WebAssembly sandbox.

## Prerequisites

- Python 3.11+
- [Friday CLI](https://github.com/atlas-ai/friday) installed and configured
- Docker (the build pipeline runs inside a container)

## Quickstart

Create a file named `agent.py`:

```python
from friday_agent_sdk import agent, ok, AgentContext
from friday_agent_sdk._bridge import Agent  # componentize-py requires this import

@agent(
    id="my-analyser",
    version="1.0.0",
    description="Analyses text with an LLM",
)
def execute(prompt: str, ctx: AgentContext):
    # Call the host's LLM provider — no API key needed
    result = ctx.llm.generate(
        messages=[{"role": "user", "content": f"Summarise this: {prompt}"}],
        model="anthropic:claude-haiku-4-5",
    )
    return ok({"summary": result.text})
```

Build the agent:

```bash
# The build runs in Docker via the Friday daemon
atlas agent build ./agent.py
```

Or use the HTTP API directly:

```bash
curl -s -X POST http://localhost:8080/api/agents/build \
  -F "files=@agent.py" | jq .
```

Add to your `workspace.yml`:

```yaml
agents:
  - id: my-analyser
    type: user
```

Test it in Friday's web UI or via CLI:

```bash
atlas prompt "my-analyser: Analyse this codebase for bugs"
```

## Documentation

- [**Tutorial: Your First Friday Agent**](docs/tutorial/your-first-agent.md) — Complete walkthrough from zero to running agent
- **How-to Guides** — Task-focused recipes for common patterns
  - [Call LLMs from your agent](docs/how-to/call-llms.md)
  - [Make HTTP requests](docs/how-to/make-http-requests.md)
  - [Use MCP tools](docs/how-to/use-mcp-tools.md)
  - [Handle structured input](docs/how-to/handle-structured-input.md)
  - [Stream progress updates](docs/how-to/stream-progress.md)
  - [Return artifacts and outline references](docs/how-to/return-artifacts.md)
- [**API Reference**](docs/reference/) — Complete decorator, context, and capability documentation
- [**How Friday Agents Work**](docs/explanation/how-agents-work.md) — Architecture, WASM sandbox, and design decisions

## Installation

The SDK is a compile-time dependency only. It is compiled into your WASM binary by `componentize-py`. You do not install it into a virtual environment for runtime use.

During development, you will want the SDK available for type checking and IDE support:

```bash
cd packages/python
pip install -e .  # or uv pip install -e .
```

## Examples

See the [`examples/`](examples/) directory for complete agents ranging from minimal to production-grade:

| Example             | Demonstrates                                               |
| ------------------- | ---------------------------------------------------------- |
| `echo-agent`        | Minimal agent — just returns input                         |
| `llm-http-agent`    | `ctx.llm.generate()` and `ctx.http.fetch()`                |
| `tools-agent`       | `ctx.tools.list()` and `ctx.tools.call()`                  |
| `time-agent`        | MCP server configuration and tool usage                    |
| `jira-agent`        | Structured input parsing with `parse_operation()`          |
| `bb-agent`          | Bitbucket PR operations — production HTTP patterns         |
| `claude-code-agent` | Full coding agent with fallbacks, artifacts, and reasoning |

Each example includes a compiled `agent.wasm` and `agent-js/` directory for reference.

## Testing

Run the conformance tests that validate your agent against the JSON Schema contracts:

```bash
vp test  # from the repo root, or:
cd packages/conformance && vp test
```

Run unit tests for the Python SDK:

```bash
cd packages/python
pytest
```

## The WIT Contract

The Python SDK implements the `friday:agent` WIT interface defined in `packages/wit/agent.wit`. Key exports your agent must provide:

```wit
export get-metadata: func() -> string;  // Returns JSON metadata
export execute: func(prompt: string, context: string) -> agent-result;
```

The `@agent` decorator and SDK bridge handle this for you. See the [WIT file](../wit/agent.wit) for the full contract including host capabilities (`llm-generate`, `http-fetch`, `call-tool`, etc.).

## Advanced Usage

### Custom Entry Points

If your agent file is not named `agent.py`, specify the entry point via the API:

```bash
curl -s -X POST http://localhost:8080/api/agents/build \
  -F "files=@main.py;filename=main.py" \
  -F "entry_point=main" \
  | jq .
```

### Docker Compose Ports

When Friday runs via docker-compose, services use different host ports:

| Service       | Host Port | Container Port |
| ------------- | --------- | -------------- |
| Daemon API    | `18080`   | `8080`         |
| Playground UI | `15200`   | `5200`         |
| Link (auth)   | `13100`   | `3100`         |

### Agent Persistence

Built agents survive container restarts. To start fresh:

```bash
docker compose down -v && docker compose up -d
```

## Limitations

- **No native extensions** — The WASM sandbox blocks C extensions (pydantic-core, numpy, etc.). Use host capabilities instead.
- **No streaming LLM responses** — Requires WASI 0.3 (expected late 2026).
- **One agent per module** — Each `.py` file builds to one WASM component.
- **5MB HTTP response limit** — Matches Friday's platform webfetch limit.

## Troubleshooting

**Build fails with "componentize-py not found"**
The build runs inside the Friday daemon's Docker container. Ensure your daemon is running: `atlas daemon status`

**Agent not appearing after build**
Agents should be immediately discoverable at `GET /api/agents`. If not, trigger a rescan:

```bash
curl -X POST http://localhost:8080/api/agents/reload
```

When running via docker-compose, use port `18080` for the daemon API.

**Build returns 400 error**
The build API returns HTTP 400 for user errors with a specific phase:

```json
{ "ok": false, "phase": "compile", "error": "SyntaxError: ..." }
```

Phases: `"compile"` (Python syntax), `"transpile"` (jco WASM-to-JS), `"validate"` (metadata schema), `"write"` (filesystem).

**Import errors in IDE but build works**
The `friday_agent_sdk` is compiled into WASM — your IDE needs it installed locally (`pip install -e .`) for type checking, but this is separate from the WASM build.

## Licence

MIT
