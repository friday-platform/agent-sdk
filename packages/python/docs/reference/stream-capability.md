# ctx.stream

Stream capability wrapper for emitting progress events and intents to the Friday UI.

## Class: StreamEmitter

```python
class StreamEmitter:
    def emit(self, event_type: str, data: dict | str) -> None: ...
    def progress(self, content: str, *, tool_name: str | None = None) -> None: ...
    def intent(self, content: str) -> None: ...
```

## Methods

### emit()

Emit a raw stream event to the host.

**Parameters:**

| Parameter    | Type          | Required | Description                                        |
| ------------ | ------------- | -------- | -------------------------------------------------- |
| `event_type` | `str`         | Yes      | Event type identifier                              |
| `data`       | `dict \| str` | Yes      | Event payload (dict serialised to JSON, or string) |

**Example:**

```python
ctx.stream.emit("custom-phase", {"step": 3, "total": 10})
ctx.stream.emit("debug", "Processing complete")
```

### progress()

Emit a `data-tool-progress` event for UI progress display.

**Parameters:**

| Parameter   | Type          | Required | Default | Description                  |
| ----------- | ------------- | -------- | ------- | ---------------------------- |
| `content`   | `str`         | Yes      | —       | Progress message             |
| `tool_name` | `str \| None` | No       | `None`  | Tool identifier for grouping |

**Example:**

```python
ctx.stream.progress("Starting analysis...")
ctx.stream.progress("Fetching repository data", tool_name="GitHub")
ctx.stream.progress("Analyzing code patterns", tool_name="Analyzer")
```

### intent()

Emit a `data-intent` event for high-level state changes.

**Parameters:**

| Parameter | Type  | Required | Description        |
| --------- | ----- | -------- | ------------------ |
| `content` | `str` | Yes      | Intent description |

**Example:**

```python
ctx.stream.intent("Discovering repository structure")
ctx.stream.intent("Identifying security issues")
ctx.stream.intent("Generating recommendations")
```

## Common Usage Patterns

### Phase-Based Progress

```python
def execute(prompt, ctx):
    ctx.stream.progress("Phase 1: Parsing input")
    config = parse_input(prompt)

    ctx.stream.progress("Phase 2: Fetching data", tool_name="GitHub")
    data = ctx.tools.call("fetch_repo", config)

    ctx.stream.progress("Phase 3: Analysing", tool_name="LLM")
    analysis = ctx.llm.generate(...)

    ctx.stream.progress("Phase 4: Finalizing")
    return ok({"result": analysis.text})
```

### Intent for State Changes

```python
def execute(prompt, ctx):
    ctx.stream.intent("Understanding task requirements")
    requirements = extract_requirements(prompt)

    ctx.stream.intent("Planning approach")
    plan = create_plan(requirements)

    ctx.stream.intent("Executing plan")
    for step in plan.steps:
        ctx.stream.progress(f"Step {step.number}: {step.description}")
        execute_step(step)

    ctx.stream.intent("Finalizing results")
    return ok({"completed": True})
```

### Tool-Associated Progress

```python
def execute(prompt, ctx):
    ctx.stream.progress("Initializing", tool_name="Setup")

    ctx.stream.progress("Querying database", tool_name="PostgreSQL")
    rows = ctx.tools.call("query", {"sql": "SELECT ..."})

    ctx.stream.progress("Processing results", tool_name="Processor")
    processed = [transform(r) for r in rows]

    ctx.stream.progress("Storing analysis", tool_name="Storage")
    ctx.http.fetch(..., method="POST", body=json.dumps(processed))

    ctx.stream.progress("Complete", tool_name="Setup")
    return ok({"count": len(processed)})
```

### Fallback When Unavailable

In test contexts without a host, `ctx.stream` is a no-op stub that safely ignores calls. You can call it unconditionally:

```python
def execute(prompt, ctx):
    ctx.stream.progress("Starting...")

    # Work...

    ctx.stream.progress("Complete")
    return ok({"done": True})
```

## Emitting During Long Operations

`ctx.stream.progress()` returns immediately — it does not wait for the host to process the event. Emit before expensive operations so the UI updates right away:

```python
ctx.stream.progress("Starting LLM call...")  # Sent immediately

# This blocks until the full response is ready
result = ctx.llm.generate(messages, model="claude-sonnet-4-6")

# Back in your code — emit the next update
ctx.stream.progress("LLM complete")  # Sent now
```

## Event Types

Standard types used by Friday:

| Type                 | Usage                                     |
| -------------------- | ----------------------------------------- |
| `data-tool-progress` | Agent progress updates (use `progress()`) |
| `data-intent`        | High-level state changes (use `intent()`) |
| `data-error`         | Error events (usually emitted by host)    |

Custom types can be emitted via `emit()` but may not have UI handlers.

## Best Practices

- **Emit before expensive operations** — Warn users before long LLM calls
- **Use tool_name for grouping** — Helps UI organize progress by component
- **Keep messages concise** — 50-100 characters ideal for UI display
- **Avoid tight loop emission** — Batch or debounce high-frequency updates
- **Prefer intent for phases, progress for detail** — Two-level hierarchy
- **Safe to call unconditionally** — `ctx.stream` is always initialized (stub in tests)

## When to Emit

| Scenario           | Method                    | Example                            |
| ------------------ | ------------------------- | ---------------------------------- |
| Starting a phase   | `intent()`                | "Analysing repository"             |
| Detailed progress  | `progress()`              | "Fetching 50 files..."             |
| Tool-specific work | `progress(tool_name=...)` | tool_name="GitHub"                 |
| Fallback scenarios | `progress()`              | "Retrying with alternate model..." |
| Completion         | `intent()`                | "Analysis complete"                |

## See Also

- [How to Stream Progress](../how-to/stream-progress.md) — Task-oriented guide
- [How Friday Agents Work](../explanation/how-agents-work.md) — JSPI async bridging
