# claude-code-agent

The most complete example — a multi-phase agent that extracts structured
intent from a free-form prompt, picks a model based on effort, runs Claude
Code through the host's LLM provider, persists the result as an artifact,
and streams progress events along the way. Read this last.

**Demonstrates:**

- `ctx.llm.generate_object(messages, schema=…)` for typed extraction with
  Haiku as a cheap pre-processor
- `ctx.llm.generate(model=…, provider_options=…)` to invoke a non-text
  model (here: `claude-code:claude-{opus,sonnet}-4-6`) with effort-based
  selection and a fallback model
- `ctx.stream.progress(msg, tool_name=…)` per phase for incremental UI
- Best-effort artifact creation through `ctx.http.fetch()` — failures are
  swallowed so storage hiccups don't fail the run
- 3-level structured-output extraction: provider object → JSON in the text
  → wrapped fallback
- Rich `@agent` metadata: `display_name`, `summary`, `description`,
  `examples`, `constraints`, `environment.required` / `optional`,
  `use_workspace_skills=True`

**Required env vars:**

| Var                  | Purpose                                                                |
| -------------------- | ---------------------------------------------------------------------- |
| `ANTHROPIC_API_KEY`  | Required — Claude API access for the underlying claude-code provider   |
| `GH_TOKEN`           | Optional — needed only if the prompt asks the agent to clone a repo    |

## Prompt

Free-form natural language. Example prompts:

- "Read and analyze the package.json file"
- "Clone owner/repo and write a TypeScript function that parses RFC 3339 timestamps"
- "Debug the off-by-one in src/parse.ts"

The pre-processing phase classifies effort (`low` → Sonnet/Haiku, `medium` →
Sonnet, `high` → Opus) and extracts a `repo` reference if cloning is mentioned.

## Run it

```bash
# 1. Install the SDK (once)
pip install friday-agent-sdk

# 2. Register with your local Friday daemon
atlas agent register ./packages/python/examples/claude-code-agent

# 3. Execute
atlas agent exec claude-code "Explain what packages/python/friday_agent_sdk/_bridge.py does"
```

Expected output: an `ok()` result whose payload is either the structured
output (when an `output_schema` is configured on the agent) or
`{"response": <markdown summary>}`. If artifact creation succeeded, the
result also carries an `ArtifactRef` in `extras.artifact_refs`.

See [`../README.md`](../README.md) for the full examples index and
[`../../README.md`](../../README.md) for the daemon quickstart.
