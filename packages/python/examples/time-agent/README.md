# time-agent

Declares an MCP server in the `@agent` decorator and calls tools from it.
The server used here is `mcp-server-time` (run via `uvx`), but the same
pattern applies to any stdio MCP server.

**Demonstrates:**

- The `mcp=` decorator parameter — registering an MCP server alongside the
  agent so the daemon spawns it on demand
- Calling MCP tools through `ctx.tools.call()` exactly like host tools
- Recovering from a bad tool call without crashing the agent

**Required env vars:** none. Requires `uvx` available on `$PATH` (the daemon
uses it to launch `mcp-server-time`).

## Prompt commands

| Prompt                          | Path                                                               |
| ------------------------------- | ------------------------------------------------------------------ |
| `discover`                      | Lists all MCP tool names visible to the agent                      |
| `now`                           | Calls `get_current_time` for UTC                                   |
| `convert <time> <from> to <to>` | Calls `convert_time`, e.g. `convert 12:00 UTC to America/New_York` |
| `combo`                         | Chains `get_current_time` then `convert_time`                      |
| `bad-tool`                      | Tries a nonexistent tool, returns the `ToolCallError` as `ok`      |
| `bad-tool-then-now`             | Recovers after a failing call and continues with `now`             |

## Run it

```bash
# 1. Install the SDK (once)
pip install friday-agent-sdk

# 2. Register with your local Friday daemon
atlas agent register ./packages/python/examples/time-agent

# 3. Execute
atlas agent exec time-agent "now"
atlas agent exec time-agent "convert 12:00 UTC to America/New_York"
```

See [`../README.md`](../README.md) for the full examples index and
[`../../README.md`](../../README.md) for the daemon quickstart.
