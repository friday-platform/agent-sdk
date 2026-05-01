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

> **Daemon ports.** Friday exposes two HTTP services: the **daemon API** and **Friday Studio**.
> The defaults depend on how you ran Friday:
>
> | Mode                | Daemon API | Friday Studio |
> | ------------------- | ---------- | ------------- |
> | Running from source | `:8080`    | `:5200`       |
> | Installer / Docker  | `:18080`   | `:15200`      |
>
> Examples in this README use the **source-code** ports. If you installed Friday via
> the installer or Docker, replace `8080` → `18080` and `5200` → `15200`.

## Quickstart

Install the SDK from PyPI:

```bash
pip install friday-agent-sdk
# or, with uv:
uv add friday-agent-sdk
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

The SDK is published to PyPI as [`friday-agent-sdk`](https://pypi.org/project/friday-agent-sdk/):

```bash
pip install friday-agent-sdk
# or with uv
uv add friday-agent-sdk
```

To install from a clone of this repo (e.g. when working on the SDK itself):

```bash
cd packages/python
uv sync --all-extras --dev
# or: pip install -e .
```

## Examples

See [`examples/`](examples/) for complete agents ranging from minimal to production-grade.
[`examples/README.md`](examples/README.md) has the full annotated index, including required env vars.

| Example                                            | Demonstrates                                                           |
| -------------------------------------------------- | ---------------------------------------------------------------------- |
| [`echo-agent`](examples/echo-agent/)               | The minimum viable agent — start here                                  |
| [`context-inspector`](examples/context-inspector/) | Inspect every `AgentContext` field as JSON — useful for E2E debugging  |
| [`llm-http-agent`](examples/llm-http-agent/)       | `ctx.llm.generate()` and `ctx.http.fetch()` happy and error paths      |
| [`tools-agent`](examples/tools-agent/)             | `ctx.tools.list()`, `ctx.tools.call()`, and `ctx.stream.progress()`    |
| [`time-agent`](examples/time-agent/)               | Declare an MCP server via the `mcp=` decorator and call a tool from it |
| [`bash-test-agent`](examples/bash-test-agent/)     | Bash tool capabilities — stdout/stderr/exit/cwd/env/multi-command      |
| [`jira-agent`](examples/jira-agent/)               | `parse_operation()` dispatch across Jira REST API v3 operations        |
| [`gh-agent`](examples/gh-agent/)                   | GitHub PR operations — clone, view, diff, review, follow-ups           |
| [`bb-agent`](examples/bb-agent/)                   | Bitbucket equivalent of `gh-agent` — production HTTP patterns          |
| [`claude-code-agent`](examples/claude-code-agent/) | Full multi-phase agent: structured extraction, fallbacks, artifacts    |

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
The `friday_agent_sdk` package must be installed in your active Python environment (`pip install friday-agent-sdk`, or `pip install -e .` when working from a clone) for type checking and autocomplete.

## License

MIT
