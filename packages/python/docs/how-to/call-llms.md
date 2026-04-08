# How to Call LLMs from Your Agent

Route LLM calls through Friday's provider registry instead of importing API clients directly.

> **New here?** See [Your First Friday Agent](../tutorial/your-first-agent.md#step-3-build-and-test) for how to build and run your agent.

## Basic Generation

Use `ctx.llm.generate()` for text completion:

```python
from friday_agent_sdk import agent, ok

@agent(id="writer", version="1.0.0", description="Writes documentation")
def execute(prompt, ctx):
    result = ctx.llm.generate(
        messages=[{"role": "user", "content": f"Write docs for: {prompt}"}],
        model="anthropic:claude-sonnet-4-6",
    )
    return ok({"output": result.text})
```

## Model Resolution

You can specify models in three ways:

```python
# Fully qualified — uses this exact model
ctx.llm.generate(..., model="anthropic:claude-sonnet-4-6")

# Bare model name with decorator provider — resolves automatically
@agent(..., llm={"provider": "anthropic", "model": "claude-sonnet-4-6"})
def execute(prompt, ctx):
    # No model arg — uses decorator default
    result = ctx.llm.generate(...)

    # Override per-call
    result = ctx.llm.generate(..., model="claude-haiku-4-5")
```

Resolution cascade:

1. Fully qualified per-call (`provider:model`) — use directly
2. Bare per-call + decorator provider — resolve
3. No per-call model + decorator default — use default
4. Nothing configured — error

## Structured Output

Use `ctx.llm.generate_object()` for JSON Schema-constrained output:

```python
schema = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "complexity": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "required": ["title", "complexity"],
}

result = ctx.llm.generate_object(
    messages=[{"role": "user", "content": "Analyse this task"}],
    schema=schema,
    model="anthropic:claude-sonnet-4-6",
)

# result.object contains the parsed JSON
data = result.object
```

## Response Fields

The `LlmResponse` object contains:

```python
result.text          # Generated text (None for generate_object)
result.object        # Structured output dict (None for generate)
result.model         # Model identifier used (e.g., "anthropic:claude-sonnet-4-6")
result.usage         # {"prompt_tokens": 120, "completion_tokens": 250}
result.finish_reason # "stop", "length", etc.
```

## Error Handling

LLM errors raise `LlmError`:

```python
from friday_agent_sdk import LlmError, agent, err, ok

@agent(id="retry-agent", version="1.0.0", description="Retries on failure")
def execute(prompt, ctx):
    try:
        result = ctx.llm.generate(..., model="expensive-model")
    except LlmError as e:
        # Fallback to cheaper model
        result = ctx.llm.generate(..., model="claude-haiku-4-5")
    return ok({"output": result.text})
```

## Advanced Options

```python
result = ctx.llm.generate(
    messages=[...],
    model="anthropic:claude-sonnet-4-6",
    max_tokens=2000,           # Limit response length
    temperature=0.7,           # Sampling temperature (0-2)
    provider_options={          # Provider-specific passthrough
        "claude-code": {
            "systemPrompt": {"type": "custom", "content": "You are a security expert"},
        },
    },
)
```

## Why Not Import OpenAI/Anthropic Directly?

The WASM sandbox blocks native Python extensions like `pydantic-core`. The `openai` and `anthropic` packages depend on these. Host capabilities let you use the same functionality without dependency hell — Friday manages API keys, rate limits, and provider routing centrally.

## See Also

- [API reference: ctx.llm](../reference/llm-capability.md)
- [How Friday Agents Work](../explanation/how-agents-work.md) — architecture rationale
