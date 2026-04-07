# Your First Friday Agent

This tutorial takes you from an empty directory to a running agent that uses an LLM to analyse text. By the end you will have built, registered, and tested an agent in Friday.

## What You Will Build

A text analysis agent that accepts a topic and returns a structured analysis with a summary, key points, and a sentiment rating. It demonstrates:

- The `@agent` decorator for metadata
- Calling an LLM through `ctx.llm.generate_object()` for structured output
- Returning structured data with `ok()`

## Prerequisites

- Python 3.11+ installed locally (for IDE support)
- Friday CLI installed: see [Friday installation guide](https://github.com/atlas-ai/friday#installation)
- Friday daemon running (the build pipeline uses Docker internally)
- A Friday workspace with an Anthropic API key connected

Verify your setup:

```bash
atlas daemon status  # should show "running"
atlas link list      # should show "anthropic" connected
```

## Step 1: Create the Agent File

Create a new directory and a file named `agent.py`:

```bash
mkdir ~/my-first-agent
cd ~/my-first-agent
```

Open `agent.py` in your editor and add:

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
    id="text-analyser",
    version="1.0.0",
    description="Analyses text and returns structured summary, key points, and sentiment",
)
def execute(prompt: str, ctx: AgentContext):
    """Analyse the user's text using an LLM."""

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
    }

    # Call the host's LLM — your agent never sees the API key
    analysis_prompt = f"""Analyse the following text.

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

Notice what is happening here:

- The `@agent` decorator registers your function with metadata Friday uses for discovery
- `ctx.llm.generate_object()` sends a request to the host's LLM registry — you specify the model and schema, Friday handles the API key and provider routing
- `ok()` wraps your structured data in the result format Friday expects

## Step 2: Build the Agent

The build pipeline compiles your Python to WASM using `componentize-py`, then transpiles to JavaScript with `jco`. This happens inside the Friday daemon's Docker container.

From the same directory as `agent.py`:

```bash
atlas agent build ./agent.py
```

You will see output showing the build steps. This stores your agent in Friday's internal registry.

## Step 3: Register in Your Workspace

Open your workspace's `workspace.yml` (usually in `~/.atlas/workspaces/<name>/` or your project directory). Add the agent:

```yaml
agents:
  - id: text-analyser
    type: user
```

The `user:` prefix is added automatically — you specify `text-analyser`, Friday resolves it to `user:text-analyser`.

## Step 4: Test the Agent

Start Friday's web UI (or use the CLI):

```bash
atlas prompt "text-analyser: The new feature shipped on time and customers are reporting significantly faster load times. Support tickets are down 40%."
```

You will see Friday's planner delegate to your agent, and after a moment:

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
atlas prompt "text-analyser: The server crashed twice today. The database is throwing connection errors and the logs are incomprehensible."
```

Notice your agent automatically classifies this as `"sentiment": "negative"`.

## Step 5: Iterate

Edit `agent.py` to change the model or adjust the schema. After each edit:

```bash
atlas agent build ./agent.py
```

The new build immediately replaces the previous version in the agent registry. Friday uses semantic versioning: rebuild with a higher version to keep old versions available for rollback.

```python
@agent(
    id="text-analyser",
    version="1.0.1",  # Bumped from 1.0.0
    description="Analyses text with an LLM",
)
```

Both versions are stored, but Friday resolves `text-analyser` to the latest semver version (`1.0.1`).

Test again. This cycle — edit, build, test — is your development loop.

## What You Have Learned

- The `@agent` decorator registers metadata Friday uses for discovery
- `ctx.llm.generate()` and `ctx.llm.generate_object()` route through the host's provider registry
- `ok()` returns structured data; `err()` returns error messages
- The build pipeline runs in Docker via the Friday daemon
- `type: user` in `workspace.yml` activates your agent

## Next Steps

- [Call LLMs with different models and options](../how-to/call-llms.md)
- [Make HTTP requests to external APIs](../how-to/make-http-requests.md)
- [Use MCP tools like GitHub or databases](../how-to/use-mcp-tools.md)
- [Stream progress updates during long operations](../how-to/stream-progress.md)
- [Handle structured input from Friday's planner](../how-to/handle-structured-input.md)
- Read [How Friday Agents Work](../explanation/how-agents-work.md) to understand the WASM sandbox and host capabilities architecture

---

## Advanced Topics

### Using the HTTP API Directly

For CI/CD pipelines or automation:

```bash
curl -s -X POST http://localhost:8080/api/agents/build \
  -F "files=@agent.py" \
  | jq .
```

Error responses include the phase that failed (`compile`, `transpile`, `validate`, or `write`):

```json
{
  "ok": false,
  "phase": "compile",
  "error": "SyntaxError: invalid syntax at line 15"
}
```

### Running with Docker Compose

When Friday runs via docker-compose, the daemon is at port `18080` instead of `8080`:

```bash
curl -s -X POST http://localhost:18080/api/agents/build -F "files=@agent.py"
```

### Troubleshooting

**"anthropic not connected"**
Connect your Anthropic API key in Friday: `atlas link add anthropic`

**"agent not found"**
Check the build output — verify the agent ID matches what you registered in `workspace.yml`. If using docker-compose, the daemon is at port `18080`.

**Build fails with syntax errors**
The SDK uses pure Python dataclasses — no Pydantic. Ensure your type hints are standard library only.

**Build returns 400**
Your `@agent` decorator metadata failed validation. Required fields: `id`, `version`, `description`.

**"componentize-py" errors about imports**
Only the Python standard library is available inside the WASM sandbox. You cannot `import requests` or `import openai`. Use `ctx.http` and `ctx.llm` instead.

## The Complete Code

Your final `agent.py`:

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
    id="text-analyser",
    version="1.0.0",
    description="Analyses text and returns structured summary, key points, and sentiment",
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
    }

    analysis_prompt = f"""Analyse the following text.

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

Congratulations — you have built your first Friday agent.
