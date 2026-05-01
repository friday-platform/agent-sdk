# llm-http-agent

Exercises `ctx.llm.generate()` and `ctx.http.fetch()` — both happy and error
paths — by routing on the prompt prefix.

**Demonstrates:**

- `ctx.llm.generate()` success and `LlmError` handling
- `ctx.http.fetch()` success and `HttpError` handling
- Prompt-prefix dispatch as a quick way to exercise multiple paths from one
  agent during E2E testing

**Required env vars:** an LLM provider key (Anthropic / OpenAI / Google)
configured in the **daemon's** `.env` — the agent itself never reads keys.

## Prompt prefixes

| Prefix       | Path                                                          |
| ------------ | ------------------------------------------------------------- |
| `llm:`       | LLM happy path (`model="test-model"`)                         |
| `llm-fail:`  | LLM error path (`model="fail-model"`, expects `LlmError`)     |
| `http:`      | HTTP happy path (fetches `https://example.com/<rest>`)        |
| `http-fail:` | HTTP error path (fetches `https://fail.example.com/<rest>`)   |

Anything without a recognised prefix returns an `err()` result.

## Run it

```bash
# 1. Install the SDK (once)
pip install friday-agent-sdk

# 2. Register with your local Friday daemon
atlas agent register ./packages/python/examples/llm-http-agent

# 3. Execute one of the prefixes
atlas agent exec llm-http-agent "llm:summarize this sentence"
atlas agent exec llm-http-agent "http:"
atlas agent exec llm-http-agent "http-fail:"
```

See [`../README.md`](../README.md) for the full examples index and
[`../../README.md`](../../README.md) for the daemon quickstart.
