# ctx.llm

LLM capability wrapper for routing generation requests through Friday's provider registry.

## Class: Llm

```python
class Llm:
    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        provider_options: dict | None = None,
    ) -> LlmResponse: ...

    def generate_object(
        self,
        messages: list[dict[str, str]],
        schema: dict,
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        provider_options: dict | None = None,
    ) -> LlmResponse: ...
```

## Methods

### generate()

Generate text from an LLM.

**Parameters:**

| Parameter          | Type                   | Required | Description                                     |
| ------------------ | ---------------------- | -------- | ----------------------------------------------- | --------------------------------------------- |
| `messages`         | `list[dict[str, str]]` | Yes      | Conversation messages with `role` and `content` |
| `model`            | `str                   | None`    | No                                              | Model identifier (resolution cascade applies) |
| `max_tokens`       | `int                   | None`    | No                                              | Maximum tokens to generate                    |
| `temperature`      | `float                 | None`    | No                                              | Sampling temperature (0.0 - 2.0)              |
| `provider_options` | `dict                  | None`    | No                                              | Provider-specific options passthrough         |

**Returns:** `LlmResponse`

**Raises:** `LlmError` on generation failure

**Example:**

```python
result = ctx.llm.generate(
    messages=[{"role": "user", "content": "Summarize this article"}],
    model="anthropic:claude-sonnet-4-6",
    max_tokens=1000,
    temperature=0.7,
)
print(result.text)
```

### generate_object()

Generate structured output conforming to a JSON Schema.

**Parameters:**

| Parameter          | Type                   | Required | Description                      |
| ------------------ | ---------------------- | -------- | -------------------------------- | ------------------------- |
| `messages`         | `list[dict[str, str]]` | Yes      | Conversation messages            |
| `schema`           | `dict`                 | Yes      | JSON Schema for output structure |
| `model`            | `str                   | None`    | No                               | Model identifier          |
| `max_tokens`       | `int                   | None`    | No                               | Maximum tokens            |
| `temperature`      | `float                 | None`    | No                               | Sampling temperature      |
| `provider_options` | `dict                  | None`    | No                               | Provider-specific options |

**Returns:** `LlmResponse` with `.object` populated

**Raises:** `LlmError` on generation failure

**Example:**

```python
schema = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary"],
}

result = ctx.llm.generate_object(
    messages=[{"role": "user", "content": "Analyze this"}],
    schema=schema,
    model="anthropic:claude-haiku-4-5",
)

data = result.object  # Parsed JSON object
print(data["summary"])
print(data.get("tags", []))
```

## Model Resolution

Resolution cascade (first match wins):

1. **Fully qualified per-call** — `model="anthropic:claude-sonnet-4-6"` used directly
2. **Bare per-call + decorator default** — `model="claude-sonnet-4-6"` + `@agent(llm={"provider": "anthropic"})` resolved to full identifier
3. **Decorator default only** — `@agent(llm={"provider": "anthropic", "model": "claude-sonnet-4-6"})` used when no model specified
4. **Error** — No model specified and no decorator default

## LlmResponse

```python
@dataclass
class LlmResponse:
    text: str | None           # Generated text (None for generate_object)
    object: dict | None        # Structured output dict (None for generate)
    model: str                 # Model identifier used (e.g., "anthropic:claude-sonnet-4-6")
    usage: dict                # {"prompt_tokens": 120, "completion_tokens": 250}
    finish_reason: str         # "stop", "length", "content_filter", etc.
```

## Error Handling

```python
from friday_agent_sdk import LlmError, agent, err, ok

@agent(id="resilient", version="1.0.0", description="Handles LLM failures")
def execute(prompt, ctx):
    try:
        result = ctx.llm.generate(..., model="expensive-model")
    except LlmError as e:
        # Error message from host (e.g., "Rate limit exceeded", "Invalid API key")
        return err(f"Primary model failed: {e}")

    return ok({"output": result.text})
```

## Provider Options

Pass provider-specific configuration:

```python
result = ctx.llm.generate(
    messages=[...],
    model="claude-code:sonnet",
    provider_options={
        "systemPrompt": {
            "type": "preset",
            "preset": "claude_code",
        },
        "effort": "high",
        "repo": "owner/repo",
    },
)
```

Options vary by provider. Common patterns:

**Claude Code provider:**

- `systemPrompt` — Either `{"type": "preset", "preset": "..."}` or `{"type": "custom", "content": "..."}`
- `effort` — `"low"`, `"medium"`, `"high"`
- `fallbackModel` — Model to use if primary fails
- `repo` — Repository to clone and work in

## Message Format

```python
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"},
    {"role": "assistant", "content": "Hi there!"},
    {"role": "user", "content": "Analyze this code..."},
]
```

Valid roles: `system`, `user`, `assistant`

## Limitations

- **No streaming responses** — Full response returned as string; streaming may be added in a future protocol revision
- **Synchronous only** — `generate()` blocks until the complete response is ready
- **5MB implicit limit** — Via platform constraints on response size

## Why Host-Managed?

Host-provided LLM calls are preferred over direct `openai`/`anthropic` usage even though agents run as native processes:

- **Credential management** — Friday injects API keys; your agent code never holds them
- **Rate limiting and quotas** — The host enforces token budgets and retries
- **Provider routing** — Friday selects the right provider based on model ID
- **Audit logging** — All generation calls are logged
- **Fallback models** — The host can automatically downgrade on rate-limit errors

## See Also

- [How to Call LLMs](../how-to/call-llms.md) — Task-oriented guide
- [AgentContext](agent-context.md) — Parent context object
- [LlmError](exceptions.md) — Exception type
