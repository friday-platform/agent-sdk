# Your First Friday Agent

Build a text analysis agent, from an empty directory to a running result. By the
end you will have built and tested an agent inside Friday's Docker environment.

## What You Will Build

A text analysis agent that accepts a topic and returns a structured analysis
with a summary, key points, and a sentiment rating. It demonstrates:

- The `@agent` decorator for metadata
- Calling an LLM through `ctx.llm.generate_object()` for structured output
- Returning structured data with `ok()`

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) with Compose
- A text editor
- An Anthropic API key

> **Tip:** Installing Python 3.11+ locally gives your editor autocomplete and
> type checking for the SDK. The build itself runs inside Docker — you do not
> need Python on your machine.

## Step 1: Start the Platform

Create a `.env` file next to your `docker-compose.yml`:

```env
ANTHROPIC_API_KEY=sk-ant-...
```

Start Friday:

```bash
docker compose up -d
```

Wait for the startup banner in the logs:

```bash
docker compose logs -f platform
```

```
================================================================
  Friday Platform is ready!

  Friday Studio:       http://localhost:15200
  Daemon API:          http://localhost:18080
================================================================
```

Press `Ctrl-C` to stop tailing. The platform keeps running in the background.

## Step 2: Create the Agent File

Friday watches the `agents/` directory next to your `docker-compose.yml`. Each
subdirectory becomes an agent.

Create the directory and open `agent.py` in your editor:

```bash
mkdir -p agents/text-analyzer
```

Write `agents/text-analyzer/agent.py`:

```python
from dataclasses import dataclass
from friday_agent_sdk import agent, ok, AgentContext
from friday_agent_sdk._bridge import Agent  # componentize-py requires this import


@dataclass
class AnalysisResult:
    summary: str
    key_points: list[str]
    sentiment: str  # "positive", "negative", or "neutral"


@agent(
    id="text-analyzer",
    version="1.0.0",
    description="Analyzes text and returns structured summary, key points, and sentiment",
)
def execute(prompt: str, ctx: AgentContext):
    """Analyze the user's text using an LLM."""

    # Define the schema for structured output
    output_schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "key_points": {
                "type": "array",
                "items": {"type": "string"},
            },
            "sentiment": {
                "type": "string",
                "enum": ["positive", "negative", "neutral"],
            },
        },
        "required": ["summary", "key_points", "sentiment"],
        "additionalProperties": False,
    }

    # Call the host's LLM — your agent never sees the API key
    analysis_prompt = f"""Analyze the following text.

Text:
{prompt}

Provide a concise summary, 3-5 key points, and an overall sentiment."""

    result = ctx.llm.generate_object(
        messages=[{"role": "user", "content": analysis_prompt}],
        schema=output_schema,
        model="anthropic:claude-haiku-4-5",  # Fast and cost-effective
    )

    # result.object contains the parsed JSON matching our schema
    return ok(result.object)
```

Three things to notice:

- The `@agent` decorator registers your function with metadata Friday uses for
  discovery.
- `ctx.llm.generate_object()` sends a request to the host's LLM registry — you
  specify the model and schema, Friday handles the API key and provider routing.
- `ok()` wraps your structured data in the result format Friday expects.

## Step 3: Build and Test

Restart the platform to build your agent:

```bash
docker compose restart platform
```

The daemon compiles every agent in `agents/` on startup. Verify the build
succeeded:

```bash
docker compose logs platform | grep -i "built agent"
# Built agent text-analyzer@1.0.0 from source
```

Test your agent with curl against the playground API on port `15200`:

```bash
curl -s -X POST http://localhost:15200/api/execute \
  -H 'Content-Type: application/json' \
  -d '{
    "agentId": "text-analyzer",
    "input": "The new feature shipped on time and customers report faster load times. Support tickets are down 40%."
  }' | jq .
```

The response streams as SSE events. After a moment you see the result:

```json
{
  "summary": "Product launch successful with measurable performance improvements",
  "key_points": [
    "Feature shipped on schedule",
    "Load times significantly improved",
    "Support tickets decreased by 40%"
  ],
  "sentiment": "positive"
}
```

Try a different input:

```bash
curl -s -X POST http://localhost:15200/api/execute \
  -H 'Content-Type: application/json' \
  -d '{
    "agentId": "text-analyzer",
    "input": "The server crashed twice today. The database is throwing connection errors and the logs are incomprehensible."
  }' | jq .
```

Your agent classifies this as `"sentiment": "negative"`.

> **Prefer the CLI?** The `atlas` CLI is available inside the container. You can
> also test from the host if you have the CLI installed:
>
> ```bash
> # From the host
> atlas agent exec text-analyzer \
>   -i "analyze this text" \
>   --url http://localhost:15200
>
> # Or from inside the container
> docker compose exec platform atlas agent exec text-analyzer \
>   -i "analyze this text"
> ```
>
> Add `--json` for raw NDJSON output (useful for piping to `jq`).

## Step 4: Iterate

Edit `agents/text-analyzer/agent.py`, then rebuild and test:

```bash
docker compose restart platform
curl -s -X POST http://localhost:15200/api/execute \
  -H 'Content-Type: application/json' \
  -d '{"agentId": "text-analyzer", "input": "test your changes"}' | jq .
```

This cycle — edit, restart, test — is your development loop.

Bump the version to keep old builds available for rollback:

```python
@agent(
    id="text-analyzer",
    version="1.0.1",  # Bumped from 1.0.0
    description="Analyzes text with an LLM",
)
```

Both versions are stored, but Friday resolves `text-analyzer` to the latest
semver version (`1.0.1`).

## Step 5: Register in a Workspace (Optional)

To use your agent within a Friday workspace (for planner routing, signals, and
multi-agent orchestration), add it to your workspace's `workspace.yml`:

```yaml
agents:
  - id: text-analyzer
    type: user
```

Friday adds the `user:` prefix automatically — you specify `text-analyzer`,
Friday resolves it to `user:text-analyzer`. This step is not required for direct
execution.

## What You Have Learned

- The `@agent` decorator registers metadata Friday uses for discovery
- `ctx.llm.generate()` and `ctx.llm.generate_object()` route through the host's
  provider registry
- `ok()` returns structured data; `err()` returns error messages
- The build pipeline compiles Python to WASM inside Docker
- Agents in `agents/` build automatically on platform startup
- Adding `type: user` to `workspace.yml` integrates your agent into a workspace
  for planner routing

## Next Steps

- [Call LLMs with different models and options](../how-to/call-llms.md)
- [Make HTTP requests to external APIs](../how-to/make-http-requests.md)
- [Use MCP tools like GitHub or databases](../how-to/use-mcp-tools.md)
- [Stream progress updates during long operations](../how-to/stream-progress.md)
- [Handle structured input from Friday's planner](../how-to/handle-structured-input.md)
- Read [How Friday Agents Work](../explanation/how-agents-work.md) to understand
  the WASM sandbox and host capabilities architecture

---

## Advanced Topics

### Using the HTTP API Directly

For CI/CD pipelines or automation, build agents via the daemon API on port
`18080`:

```bash
curl -s -X POST http://localhost:18080/api/agents/build \
  -F "files=@agent.py" \
  | jq .
```

Error responses include the phase that failed (`compile`, `transpile`,
`validate`, or `write`):

```json
{
  "ok": false,
  "phase": "compile",
  "error": "SyntaxError: invalid syntax at line 15"
}
```

### Local Development (Without Docker)

If you run the Friday daemon directly on your machine (e.g. as a contributor),
the CLI commands work without the Docker layer:

```bash
atlas daemon status        # verify the daemon is running
atlas link list            # verify credentials are connected
atlas agent build ./agent.py
atlas agent exec text-analyzer -i "test input"
```

The daemon listens on port `8080` locally (not `18080`). See the
Friday CLI documentation for setup.

### Customizing the Agent Directory

By default, Friday watches `./agents/` next to your `docker-compose.yml`. To
use a different directory, set `AGENTS_DIR` in your `.env`:

```env
AGENTS_DIR=./my-agents
```

### Troubleshooting

**Agent not found after restart**
Check the build logs: `docker compose logs platform | grep -i "built agent"`.
Verify the agent ID matches what you pass to the execute API.

**Build fails with syntax errors**
The SDK uses pure Python dataclasses — no Pydantic. Ensure your type hints use
standard library types only.

**Build returns 400**
Your `@agent` decorator metadata failed validation. Required fields: `id`,
`version`, `description`.

**"componentize-py" errors about imports**
Only the Python standard library is available inside the WASM sandbox. You
cannot `import requests` or `import openai`. Use `ctx.http` and `ctx.llm`
instead.

**Credentials not working**
Verify your `.env` file contains `ANTHROPIC_API_KEY` and restart the platform:
`docker compose restart platform`.

## The Complete Code

Your final `agents/text-analyzer/agent.py`:

```python
from dataclasses import dataclass
from friday_agent_sdk import agent, ok, AgentContext
from friday_agent_sdk._bridge import Agent


@dataclass
class AnalysisResult:
    summary: str
    key_points: list[str]
    sentiment: str


@agent(
    id="text-analyzer",
    version="1.0.0",
    description="Analyzes text and returns structured summary, key points, and sentiment",
)
def execute(prompt: str, ctx: AgentContext):
    output_schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "key_points": {
                "type": "array",
                "items": {"type": "string"},
            },
            "sentiment": {
                "type": "string",
                "enum": ["positive", "negative", "neutral"],
            },
        },
        "required": ["summary", "key_points", "sentiment"],
        "additionalProperties": False,
    }

    analysis_prompt = f"""Analyze the following text.

Text:
{prompt}

Provide a concise summary, 3-5 key points, and an overall sentiment."""

    result = ctx.llm.generate_object(
        messages=[{"role": "user", "content": analysis_prompt}],
        schema=output_schema,
        model="anthropic:claude-haiku-4-5",
    )

    return ok(result.object)
```
