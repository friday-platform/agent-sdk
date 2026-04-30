# Friday Agent SDK for Python

Write AI agents in Python that run inside the Friday platform. Agents call LLMs, make HTTP requests, and use MCP tools through the host — no API keys or dependencies required in agent code.

## Prerequisites

- Python 3.12+
- The Friday daemon and `atlas` CLI — install via [friday-platform/friday-studio](https://github.com/friday-platform/friday-studio).
  Follow that repo's quickstart to clone, install, configure an LLM provider key,
  and run `deno task atlas daemon start --detached`. Verify it's up:
  ```bash
  curl -sf http://localhost:8080/health && echo "  daemon ok"
  ```
- An LLM provider API key (Anthropic, OpenAI, or Google) configured in the
  daemon's `.env` — see Friday Studio's `.env.example` for the full list.

## Quickstart

Install the SDK:

```bash
cd packages/python
uv pip install -e .   # or: pip install -e .
```

Create an agent directory:

```bash
mkdir -p agents/my-analyzer
```

Write `agents/my-analyzer/agent.py`:

```python
from friday_agent_sdk import agent, ok, AgentContext, run

@agent(
    id="my-analyzer",
    version="1.0.0",
    description="Analyzes text with an LLM",
)
def execute(prompt: str, ctx: AgentContext):
    result = ctx.llm.generate(
        messages=[{"role": "user", "content": f"Summarize this: {prompt}"}],
        model="anthropic:claude-haiku-4-5",
    )
    return ok({"summary": result.text})

if __name__ == "__main__":
    run()
```

Register your agent with the daemon:

```bash
atlas agent register ./agents/my-analyzer
```

Test it:

```bash
atlas agent exec my-analyzer -i "Summarize this codebase"
```

Or via the playground API:

```bash
curl -s -X POST http://localhost:5200/api/agents/my-analyzer/run \
  -H 'Content-Type: application/json' \
  -d '{"input": "Summarize this codebase"}'
```

## Documentation

- [**Tutorial: Your First Friday Agent**](docs/tutorial/your-first-agent.md) — Complete walkthrough from zero to running agent
- **How-to Guides** — Task-focused recipes for common patterns
  - [Call LLMs from your agent](docs/how-to/call-llms.md)
  - [Make HTTP requests](docs/how-to/make-http-requests.md)
  - [Use MCP tools](docs/how-to/use-mcp-tools.md)
  - [Handle structured input](docs/how-to/handle-structured-input.md)
  - [Stream progress updates](docs/how-to/stream-progress.md)
- [**API Reference**](docs/reference/) — Complete decorator, context, and capability documentation
- [**How Friday Agents Work**](docs/explanation/how-agents-work.md) — Architecture and design decisions (optional reading)

## Installation

The SDK is a normal Python package. Install it for development and execution:

```bash
cd packages/python
pip install -e .
```

## Examples

See the [`examples/`](examples/) directory for complete agents ranging from minimal to production-grade:

| Example             | Demonstrates                                         |
| ------------------- | ---------------------------------------------------- |
| `echo-agent`        | Minimal agent — just returns input                   |
| `llm-http-agent`    | `ctx.llm.generate()` and `ctx.http.fetch()`          |
| `tools-agent`       | `ctx.tools.list()` and `ctx.tools.call()`            |
| `time-agent`        | MCP server configuration and tool usage              |
| `jira-agent`        | Structured input parsing with `parse_operation()`    |
| `bb-agent`          | Bitbucket PR operations — production HTTP patterns   |
| `claude-code-agent` | Full coding agent with fallbacks and model selection |

## Testing

Run unit tests for the Python SDK:

```bash
cd packages/python
pytest
```

## Advanced usage

### Custom entry points

If your agent file is not named `agent.py`, specify the entry point during registration:

```bash
atlas agent register ./my-agent --entry main.py
```

Or via the API:

```bash
curl -s -X POST http://localhost:8080/api/agents/register \
  -H 'Content-Type: application/json' \
  -d '{"entrypoint": "/path/to/my-agent/main.py"}'
```

### Direct execution API

For CI/CD pipelines or automation, execute agents via the daemon API:

```bash
curl -s -X POST http://localhost:8080/api/agents/my-agent/run \
  -H 'Content-Type: application/json' \
  -d '{"input": "test prompt"}'
```

Error responses include the phase that failed (`prereqs`, `validate`, `write`):

```json
{ "ok": false, "phase": "validate", "error": "description is required" }
```

## Limitations

- **No streaming LLM responses** — `ctx.llm.generate()` blocks until the full response is ready
- **One agent per file** — Each `.py` file registers exactly one `@agent`
- **5MB HTTP response limit** — Matches Friday's platform webfetch limit
- **Spawn-per-call** — Each execution starts a fresh process; keep startup lightweight

## Troubleshooting

**Registration fails with "validate timeout"**
The daemon spawns your agent to collect metadata and waits up to 15s. Check that `run()` is called in `__main__` and that the daemon is running.

**Agent not appearing after registration**
Check that registration succeeded: `atlas agent list`. Agents are stored in `~/.friday/local/agents/`.

**Registration returns 400**
Your `@agent` decorator metadata failed validation. Required fields: `id`, `version`, `description`.

**Execution hangs**
The agent may not be signaling readiness before the daemon sends the execute request. Verify `run()` is called.

**Import errors in IDE**
The `friday_agent_sdk` must be installed locally (`pip install -e .`) for type checking and autocomplete.

## License

MIT
