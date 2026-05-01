# bash-test-agent

Exercises every part of the `bash` host tool so you can confirm the
host↔agent boundary is wired correctly. Treat it as a smoke test, not a
template — production agents shouldn't shell out for everything.

**Demonstrates:**

- stdout/stderr capture and exit-code propagation
- `cwd` and `env` injection into the bash subprocess
- Multi-command sequences (clone → list → cleanup)
- `parse_input(prompt)` for routing on a JSON `action`

**Required env vars:** none.

## Prompt actions

The prompt is JSON like `{"action": "<name>", ...}`.

| `action`         | What it runs                                                  |
| ---------------- | ------------------------------------------------------------- |
| `dump-prompt`    | Returns the raw prompt (first 2000 chars) — useful for debug  |
| `list-tools`     | Returns the names of all tools visible to the agent           |
| `echo`           | `echo hello`                                                  |
| `exit-code`      | `exit 42` — verifies non-zero exit codes propagate            |
| `cwd`            | `pwd` with `cwd: /tmp` — verifies working directory injection |
| `env`            | `echo $QA_TEST_VAR` with `env: {QA_TEST_VAR: ...}`            |
| `clone`          | Clones a repo from `repo_url`, lists files, cleans up         |

## Run it

```bash
# 1. Install the SDK (once)
pip install friday-agent-sdk

# 2. Register with your local Friday daemon
atlas agent register ./packages/python/examples/bash-test-agent

# 3. Execute (note the agent id is `bash-test`, not the directory name)
atlas agent exec bash-test '{"action": "echo"}'
atlas agent exec bash-test '{"action": "exit-code"}'
atlas agent exec bash-test '{"action": "cwd"}'
```

See [`../README.md`](../README.md) for the full examples index and
[`../../README.md`](../../README.md) for the daemon quickstart.
