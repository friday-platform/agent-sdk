# Result Types

Tagged union results for agent handler returns.

## Functions

### ok()

Create a success result.

```python
ok(data: object, extras: AgentExtras | None = None) -> OkResult
```

**Parameters:**

| Parameter | Type         | Required | Description                                      |
| --------- | ------------ | -------- | ------------------------------------------------ | ------------------------------ |
| `data`    | `object`     | Yes      | Serializable result data (dict, list, primitive) |
| `extras`  | `AgentExtras | None`    | No                                               | Optional metadata for the host |

**Returns:** `OkResult`

**Example:**

```python
from friday_agent_sdk import agent, ok, AgentExtras, ArtifactRef

@agent(id="success", version="1.0.0", description="Returns success")
def execute(prompt, ctx):
    # Simple result
    return ok({"answer": 42})

    # With extras
    return ok(
        {"answer": 42},
        extras=AgentExtras(reasoning="Derived from analysis"),
    )

    # With artifact reference
    return ok(
        {"analysis_id": "123"},
        extras=AgentExtras(
            artifact_refs=[
                ArtifactRef(id="123", type="analysis", summary="Complete")
            ]
        ),
    )
```

### err()

Create an error result.

```python
err(message: str) -> ErrResult
```

**Parameters:**

| Parameter | Type  | Required | Description                         |
| --------- | ----- | -------- | ----------------------------------- |
| `message` | `str` | Yes      | Error message for the host and user |

**Returns:** `ErrResult`

**Example:**

```python
from friday_agent_sdk import agent, err

@agent(id="checker", version="1.0.0", description="Checks prerequisites")
def execute(prompt, ctx):
    if "API_KEY" not in ctx.env:
        return err("API_KEY not set. Connect the provider in Friday Link.")

    if ctx.llm is None:
        return err("LLM capability not available in this context.")

    return ok({"status": "ready"})
```

## Types

### AgentResult

Union type for handler return annotations:

```python
from friday_agent_sdk import AgentResult

def execute(prompt, ctx) -> AgentResult:
    if error:
        return err("Something failed")
    return ok({"result": "success"})
```

### OkResult

Success result dataclass:

```python
@dataclass
class OkResult:
    data: object
    extras: AgentExtras | None = None
```

The `data` field is serialised to JSON by the bridge. Complex objects should be dicts or lists.

### ErrResult

Error result dataclass:

```python
@dataclass
class ErrResult:
    error: str
```

The `error` message is passed through to the host and displayed to the user.

### AgentExtras

Optional metadata for success results:

```python
@dataclass
class AgentExtras:
    reasoning: str | None = None
    artifact_refs: list[ArtifactRef] | None = None
    outline_refs: list[OutlineRef] | None = None
```

**Fields:**

- `reasoning` — Explanation of agent decisions, shown in UI for transparency
- `artifact_refs` — References to created platform artifacts
- `outline_refs` — Structured entries for conversation outline

### ArtifactRef

Reference to a platform artifact:

```python
@dataclass
class ArtifactRef:
    id: str      # Artifact identifier
    type: str    # Artifact type (e.g., "analysis", "report")
    summary: str # Human-readable summary
```

Created via Friday's `/api/artifacts` endpoint. See [How to Return Artifacts](../how-to/return-artifacts.md).

### OutlineRef

Structured reference for conversation outline:

```python
@dataclass
class OutlineRef:
    service: str       # Service identifier (e.g., "github", "analysis")
    title: str         # Display title
    content: str | None = None        # Optional content preview
    artifact_id: str | None = None    # Linked artifact
    artifact_label: str | None = None # Link label text
```

## Tagged Union Pattern

`OkResult` and `ErrResult` are distinct types. It is impossible to:

- Return success data with an error message
- Return error data with success extras
- Confuse the two in type checking

```python
from friday_agent_sdk import OkResult, ErrResult

def handle(result: AgentResult):
    match result:
        case OkResult(data, extras):
            process_success(data, extras)
        case ErrResult(error):
            handle_error(error)
```

## Serialisation

The bridge converts results to the WIT `agent-result` variant:

```wit
variant agent-result {
    ok(string),   // JSON-serialised ok.data
    err(string),  // err.error message
}
```

`AgentExtras` is serialised separately and merged by the host.

## Best Practices

- **Return structured data** — Dicts with clear field names, not raw strings
- **Provide reasoning** — Helps users understand agent decisions
- **Create artifacts for large outputs** — Persist reports, analyses, generated code
- **Use outline_refs for scannable results** — Helps navigate complex outputs
- **Handle errors early** — Validate `ctx.env`, check capabilities, return `err()` with clear messages

## Common Error Messages

| Scenario            | Message                                                 |
| ------------------- | ------------------------------------------------------- |
| Missing environment | `"{VAR} not set. Connect the provider in Friday Link."` |
| Missing capability  | `"{Capability} not available in this context."`         |
| API failure         | `"{Service} API error {code}: {details}"`               |
| Invalid input       | `"Invalid request: {reason}"`                           |
| Timeout             | `"Operation timed out after {duration}"`                |

## See Also

- [How to Return Artifacts](../how-to/return-artifacts.md) — Complete artifact creation guide
- [How to Stream Progress](../how-to/stream-progress.md) — Real-time updates during execution
