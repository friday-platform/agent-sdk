# Examples

Self-contained Friday agents you can register and run as-is. Each directory
contains a single `agent.py` — that's the whole agent.

Examples are ordered roughly from simplest to most realistic. If you've never
written a Friday agent, start with `echo-agent` and walk down.

## Running an example

```bash
# 1. Install the SDK (once)
pip install friday-agent-sdk

# 2. Register the example with your local Friday daemon
atlas agent register ./packages/python/examples/echo-agent

# 3. Execute it
atlas agent exec echo "hello world"
```

Replace `echo` and `echo-agent` with the directory and agent ID of any other
example. See [`../README.md`](../README.md) for the full quickstart and daemon-port
conventions.

## Index

### Tracer-bullet agents (no external dependencies)

| Example                                   | Demonstrates                                                                                                                | Env vars |
| ----------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- | -------- |
| [`echo-agent`](echo-agent/)               | The minimum viable agent — `@agent` + `ok()` + `run()`. Returns the prompt verbatim. Read this first.                       | none     |
| [`context-inspector`](context-inspector/) | Serializes every `AgentContext` field (`env`, `config`, `session`, `output_schema`, tools) to JSON. Useful for E2E testing. | none     |

### Capability walkthroughs

| Example                               | Demonstrates                                                                                                                             | Env vars                              |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- |
| [`llm-http-agent`](llm-http-agent/)   | `ctx.llm.generate()` and `ctx.http.fetch()` — exercises both happy and error paths via prompt prefixes (`llm:`, `http:`, `llm-fail:` …). | LLM provider key in the daemon `.env` |
| [`tools-agent`](tools-agent/)         | `ctx.tools.list()`, `ctx.tools.call()`, and `ctx.stream.progress()` — capability round-trip with error propagation.                      | none                                  |
| [`time-agent`](time-agent/)           | Declares an MCP server via the `mcp=` decorator parameter and calls a tool from it (`mcp-server-time`).                                  | `uvx` available on `$PATH`            |
| [`bash-test-agent`](bash-test-agent/) | Exercises the bash tool: stdout/stderr capture, exit codes, working directory, env injection, multi-command sequences.                   | none                                  |

### Production-shaped agents

These are realistic ports of agents Friday ships internally. Use them as
templates when you build your own integration.

| Example                                   | Demonstrates                                                                                                                                                                                                                                                                        | Env vars                                         |
| ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| [`jira-agent`](jira-agent/)               | `parse_operation()` for typed routing across multiple Jira REST API operations (issue view/search/create/update/comment/transition). Auth via Basic Auth headers; ADF-aware formatting.                                                                                             | `JIRA_SITE`, `JIRA_EMAIL`, `JIRA_API_TOKEN`      |
| [`gh-agent`](gh-agent/)                   | `parse_input()` for GitHub PR operations — clone, pr-view, pr-diff, pr-files, pr-review, inline review, follow-ups. Token plumbing via `GIT_ASKPASS` to keep secrets out of the URL.                                                                                                | `GH_TOKEN`                                       |
| [`bb-agent`](bb-agent/)                   | Bitbucket equivalent of `gh-agent` — `parse_operation()` dispatch, Bitbucket REST API v2, paginated diff/threads/files, inline review and follow-up posting.                                                                                                                        | `BITBUCKET_EMAIL`, `BITBUCKET_TOKEN`             |
| [`claude-code-agent`](claude-code-agent/) | A full multi-phase agent: extract structured intent with `generate_object()`, route to a Claude Code provider with effort-based model selection and a fallback model, persist the result as an artifact, stream progress events. The most complete example — read after the others. | `ANTHROPIC_API_KEY` (and `GH_TOKEN` for cloning) |

## Adding a new example

- One agent per directory. The file is always `agent.py`.
- Open the file with a one-line docstring saying what the example demonstrates.
- If your example needs env vars, document them in the agent docstring AND add a
  row to this index.
- Keep the agent self-contained — no helper modules. If it grows, it has
  outgrown the `examples/` directory and belongs somewhere else.
