# Your First Friday Agent

Build a text analysis agent, from an empty directory to a running result. By the end you will have registered and tested an agent inside Friday.

## What you will build

A text analysis agent that accepts a topic and returns a structured analysis with a summary, key points, and a sentiment rating. It demonstrates:

- The `@agent` decorator for metadata
- Calling an LLM through `ctx.llm.generate_object()` for structured output
- Returning structured data with `ok()`
- The `run()` entry point

## Prerequisites

- Python 3.12+ installed locally
- The Friday daemon running
- An Anthropic API key configured in the platform

> **Tip:** Installing the SDK locally (`pip install -e .`) gives your editor autocomplete and type checking.

## Step 1: Start the platform

Ensure the Friday daemon is running:

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

> **Daemon ports.** This tutorial uses the **installer / Docker** ports shown above
> (`:15200` for Studio, `:18080` for the daemon API). If you're running Friday from
> source, your defaults are `:5200` and `:8080` instead — adjust each `curl` example
> accordingly.

## Step 2: Install the SDK

```bash
cd packages/python
pip install -e .
```

## Step 3: Create the agent file

Create the directory and open `agent.py` in your editor:

```bash
mkdir -p agents/text-analyzer
```

Write `agents/text-analyzer/agent.py`:

```python
from dataclasses import dataclass
from friday_agent_sdk import agent, ok, AgentContext, run


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


if __name__ == "__main__":
    run()
```

Four things to notice:

- The `@agent` decorator registers your function with metadata Friday uses for discovery.
- `ctx.llm.generate_object()` sends a request to the host's LLM registry — you specify the model and schema, Friday handles the API key and provider routing.
- `ok()` wraps your structured data in the result format Friday expects.
- `run()` in the `__main__` block is the entry point. Without it, the agent spawns and immediately exits.

## Step 4: Register and test

Register your agent:

```bash
atlas agent register ./agents/text-analyzer
```

Test with the CLI:

```bash
atlas agent exec text-analyzer \
  -i "The new feature shipped on time and customers report faster load times. Support tickets are down 40%."
```

Or via the playground API:

```bash
curl -s -X POST http://localhost:15200/api/agents/text-analyzer/run \
  -H 'Content-Type: application/json' \
  -d '{"input": "The new feature shipped on time..."}' | jq .
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
atlas agent exec text-analyzer \
  -i "The server crashed twice today. The database is throwing connection errors."
```

## Step 5: Iterate

Edit `agents/text-analyzer/agent.py`, then re-register and test:

```bash
atlas agent register ./agents/text-analyzer
atlas agent exec text-analyzer -i "test your changes"
```

This cycle — edit, register, test — is your development loop.

Bump the version to keep old registrations available:

```python
@agent(
    id="text-analyzer",
    version="1.0.1",  # Bumped from 1.0.0
    description="Analyzes text with an LLM",
)
```

Both versions are stored, but Friday resolves `text-analyzer` to the latest semver version (`1.0.1`).

## Step 6: Register in a workspace (optional)

To use your agent within a Friday workspace (for planner routing, signals, and multi-agent orchestration), add it to your workspace's `workspace.yml`:

```yaml
agents:
  - id: text-analyzer
    type: user
```

Friday adds the `user:` prefix automatically — you specify `text-analyzer`, Friday resolves it to `user:text-analyzer`. This step is not required for direct execution.

## What you have learned

- The `@agent` decorator registers metadata Friday uses for discovery
- `ctx.llm.generate()` and `ctx.llm.generate_object()` route through the host's provider registry
- `ok()` returns structured data; `err()` returns error messages
- `run()` in `__main__` is required — without it the agent exits immediately
- `atlas agent register` stores source code and metadata; `atlas agent exec` runs it
- Adding `type: user` to `workspace.yml` integrates your agent into a workspace for planner routing

## Next steps

- [Call LLMs with different models and options](../how-to/call-llms.md)
- [Make HTTP requests to external APIs](../how-to/make-http-requests.md)
- [Use MCP tools like GitHub or databases](../how-to/use-mcp-tools.md)
- [Stream progress updates during long operations](../how-to/stream-progress.md)
- [Handle structured input from Friday's planner](../how-to/handle-structured-input.md)
- Read [How Friday Agents Work](../explanation/how-agents-work.md) to understand the architecture

---

## Advanced topics

### Using the HTTP API directly

For CI/CD pipelines or automation, register agents via the daemon API:

```bash
curl -s -X POST http://localhost:18080/api/agents/register \
  -H 'Content-Type: application/json' \
  -d '{"entrypoint": "/path/to/agents/text-analyzer/agent.py"}'
```

Error responses include the phase that failed (`prereqs`, `validate`, `write`):

```json
{
  "ok": false,
  "phase": "validate",
  "error": "description is required"
}
```

### Custom entry points

If your agent file is not named `agent.py`:

```bash
atlas agent register ./my-agent --entry main.py
```

### Local development (without Docker)

If you run the Friday daemon directly on your machine (e.g. as a contributor):

```bash
atlas daemon status        # verify the daemon is running
atlas link list            # verify credentials are connected
atlas agent register ./my-agent
atlas agent exec my-agent -i "test input"
```

In source mode the daemon listens on `:8080` and Friday Studio on `:5200` (instead
of `:18080` / `:15200` in installer mode). See the Friday CLI documentation for setup.

### Troubleshooting

**Agent not found after registration**
Check that registration succeeded: `atlas agent list`. Agents are stored in `~/.friday/local/agents/`.

**Registration fails with "validate timeout"**
The daemon spawns your agent to collect metadata and waits up to 15s. Check that `run()` is called in `__main__`.

**Registration returns 400**
Your `@agent` decorator metadata failed validation. Required fields: `id`, `version`, `description`.

**Execution hangs**
The agent may not be signaling readiness. Verify `run()` is called and the daemon is running.

**Credentials not working**
Verify your `.env` file contains `ANTHROPIC_API_KEY` and the platform is running: `docker compose ps platform`.

## The complete code

Your final `agents/text-analyzer/agent.py`:

```python
from dataclasses import dataclass
from friday_agent_sdk import agent, ok, AgentContext, run


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


if __name__ == "__main__":
    run()
```
