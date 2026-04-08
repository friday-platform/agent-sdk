# How to Stream Progress Updates

Emit progress events that appear in Friday's UI during long-running operations.

> **New here?** See [Your First Friday Agent](../tutorial/your-first-agent.md#step-3-build-and-test) for how to build and run your agent.

## Basic Progress Emission

```python
from friday_agent_sdk import agent, ok

@agent(id="long-task", version="1.0.0", description="Takes a while")
def execute(prompt, ctx):
    ctx.stream.progress("Starting analysis...")

    # Do work...
    result = ctx.llm.generate(...)

    ctx.stream.progress("Processing results...")

    # More work...
    data = process(result.text)

    ctx.stream.progress("Complete!")
    return ok({"data": data})
```

Progress appears in the Friday UI as streaming updates while your agent runs.

## Intent Emission

Emit high-level intents for significant state changes:

```python
ctx.stream.intent("Analysing repository structure")

# Walk directory tree...

ctx.stream.intent("Identifying issues")

# Run analysis...

ctx.stream.intent("Generating report")
```

## With Tool Context

Associate progress with specific tools:

```python
ctx.stream.progress("Fetching repository data", tool_name="GitHub")

# Call GitHub MCP tools...

ctx.stream.progress("Analysing code patterns", tool_name="Analyser")

# LLM analysis...

ctx.stream.progress("Creating summary", tool_name="Reporter")
```

## Real Example: Multi-Phase Agent

```python
from friday_agent_sdk import agent, ok, AgentExtras

@agent(id="analyser", version="1.0.0", description="Multi-phase analysis")
def execute(prompt, ctx):
    # Phase 1: Extract parameters
    ctx.stream.progress("Parsing request")
    params = extract_params(prompt)

    # Phase 2: LLM preprocessing
    ctx.stream.progress("Running initial analysis", tool_name="LLM")
    analysis = ctx.llm.generate(
        messages=[{"role": "user", "content": f"Analyse: {params}"}],
        model="claude-haiku-4-5",
    )

    # Phase 3: Tool calls
    ctx.stream.progress("Fetching related data", tool_name="GitHub")
    issues = ctx.tools.call("search_issues", {"query": params["query"]})

    # Phase 4: Synthesis
    ctx.stream.progress("Synthesising results", tool_name="Synthesiser")
    result = synthesise(analysis.text, issues)

    ctx.stream.progress("Analysis complete")
    return ok({
        "summary": result["summary"],
        "recommendations": result["recommendations"],
    })
```

## When to Emit

Emit progress when:

- Starting a distinct phase of work
- Before expensive operations (LLM calls, HTTP requests)
- After completing significant milestones
- When handling fallback scenarios ("Retrying with different model...")

Do not emit:

- In tight loops (debounce or batch instead)
- For trivial operations (< 100ms)
- Excessively verbose detail ("Step 1 of 50", "Step 2 of 50"...)

## Emission During JSPI Calls

Progress emits happen synchronously — they do not suspend the WASM JSPI context. This means you can emit progress while the host is processing an LLM call:

```python
ctx.stream.progress("Starting LLM call...")

# This suspends via JSPI — progress was already sent
result = ctx.llm.generate(messages, model="claude-sonnet-4-6")

# Host may have emitted its own progress during the suspend
# Now we're back in Python
ctx.stream.progress("LLM complete, processing...")
```

## Fallback When Stream Unavailable

The `ctx.stream` field may be `None` in test contexts. Handle gracefully:

```python
if ctx.stream:
    ctx.stream.progress("Working...")

# Or use a helper
def progress(ctx, msg):
    if ctx.stream:
        ctx.stream.progress(msg)

progress(ctx, "Starting...")
```

## Raw Event Emission

For custom event types, use `emit()`:

```python
ctx.stream.emit("custom-event", {"phase": "validation", "count": 42})
```

The `data` parameter accepts either a dict (JSON-serialised) or string.

## See Also

- [API reference: ctx.stream](../reference/stream-capability.md)
- [How Friday Agents Work](../explanation/how-agents-work.md) — JSPI async bridging details
