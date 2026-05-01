# tools-agent

Exercises the host-tools capability — listing tools, calling them, streaming
progress, and propagating errors.

**Demonstrates:**

- `ctx.tools.list()` and `ctx.tools.call()` round-trip
- `ctx.stream.progress()` for incremental status updates
- `ToolCallError` propagation when a tool call fails

**Required env vars:** none.

## Prompt prefixes

| Prompt          | Path                                                                   |
| --------------- | ---------------------------------------------------------------------- |
| any text        | Calls the `echo` tool with `{msg: prompt}`                             |
| `fail:<reason>` | Calls the `fail` tool to force a `ToolCallError` (returned as `err()`) |

## Run it

```bash
# 1. Install the SDK (once)
pip install friday-agent-sdk

# 2. Register with your local Friday daemon
atlas agent register ./packages/python/examples/tools-agent

# 3. Execute
atlas agent exec tools-agent "hello"
atlas agent exec tools-agent "fail:simulate a tool error"
```

Expected output: an `ok()` result with `tool_result` and `tool_count`, or an
`err()` carrying the `ToolCallError` message for the `fail:` path.

See [`../README.md`](../README.md) for the full examples index and
[`../../README.md`](../../README.md) for the daemon quickstart.
