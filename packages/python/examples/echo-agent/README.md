# echo-agent

The minimum viable Friday agent — `@agent` + `ok()` + `run()`. Returns the
prompt verbatim. Read this first if you've never written a Friday agent.

**Demonstrates:** the smallest possible agent that registers, validates, and
executes against the daemon.

**Required env vars:** none.

## Run it

```bash
# 1. Install the SDK (once)
pip install friday-agent-sdk

# 2. Register with your local Friday daemon
atlas agent register ./packages/python/examples/echo-agent

# 3. Execute
atlas agent exec echo "hello world"
```

Expected output: a result containing `"hello world"`.

See [`../README.md`](../README.md) for the full examples index and
[`../../README.md`](../../README.md) for the daemon quickstart.
