# context-inspector

Returns every field from `AgentContext` as JSON so you can verify what survives
the host round-trip. Useful as a tracer-bullet during E2E setup and when
debugging why a value isn't reaching your agent.

**Demonstrates:** `ctx.env`, `ctx.config`, `ctx.session`, `ctx.output_schema`,
and `ctx.tools.list()` — all serialised in one shot.

**Required env vars:** none.

## Run it

```bash
# 1. Install the SDK (once)
pip install friday-agent-sdk

# 2. Register with your local Friday daemon
atlas agent register ./packages/python/examples/context-inspector

# 3. Execute (the prompt is echoed back inside the JSON)
atlas agent exec context-inspector "ping"
```

Expected output: a JSON string containing `prompt`, `env`, `config`, `session`
(`id`, `workspace_id`, `user_id`, `datetime`), `output_schema`, `has_tools`,
and `tool_count`.

See [`../README.md`](../README.md) for the full examples index and
[`../../README.md`](../../README.md) for the daemon quickstart.
