# Result Types

Tagged union results for agent handler returns.

## Functions

### ok()

Create a success result.

```python
ok(data: object) -> OkResult
```

**Parameters:**

| Parameter | Type     | Required | Description                                      |
| --------- | -------- | -------- | ------------------------------------------------ |
| `data`    | `object` | Yes      | Serializable result data (dict, list, primitive) |

**Returns:** `OkResult`

**Example:**

```python
from friday_agent_sdk import agent, ok

@agent(id="success", version="1.0.0", description="Returns success")
def execute(prompt, ctx):
    return ok({"answer": 42})
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

## Tagged Union Pattern

`OkResult` and `ErrResult` are distinct types. It is impossible to:

- Return success data with an error message
- Confuse the two in type checking

```python
from friday_agent_sdk import OkResult, ErrResult

def handle(result: AgentResult):
    match result:
        case OkResult(data):
            process_success(data)
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

## Best Practices

- **Return structured data** — Dicts with clear field names, not raw strings
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

- [How to Stream Progress](../how-to/stream-progress.md) — Real-time updates during execution
