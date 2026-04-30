# Parse Utilities

Extract structured JSON from enriched prompts sent by Friday.

## Functions

### parse_input()

Extract a JSON object from a text string, with optional dataclass validation.

```python
@overload
def parse_input(prompt: str) -> dict: ...

@overload
def parse_input(prompt: str, schema: type[T]) -> T: ...

def parse_input(prompt: str, schema: type | None = None) -> Any: ...
```

**Parameters:**

| Parameter | Type           | Required | Description                          |
| --------- | -------------- | -------- | ------------------------------------ |
| `prompt`  | `str`          | Yes      | The enriched prompt text from Friday |
| `schema`  | `type \| None` | No       | Dataclass type for typed extraction  |

**Returns:** `dict` or dataclass instance

**Raises:**

- `ValueError` — No valid JSON object found in prompt
- `TypeError` — Schema is not a dataclass
- `ValueError` — JSON doesn't match dataclass (missing required fields)

**Example:**

```python
from dataclasses import dataclass
from friday_agent_sdk import parse_input

# Plain dict extraction
data = parse_input(prompt)
repo = data.get("repository")
branch = data.get("branch", "main")

# Typed extraction
@dataclass
class Config:
    repository: str
    branch: str = "main"
    dry_run: bool = False

config = parse_input(prompt, Config)
# config.repository, config.branch, config.dry_run available with types
```

### parse_operation()

Extract an operation config using a discriminator field.

```python
def parse_operation(prompt: str, schemas: dict[str, type[T]]) -> T: ...
```

**Parameters:**

| Parameter | Type                 | Required | Description                            |
| --------- | -------------------- | -------- | -------------------------------------- |
| `prompt`  | `str`                | Yes      | The enriched prompt text               |
| `schemas` | `dict[str, type[T]]` | Yes      | Map of operation name → dataclass type |

**Returns:** Dataclass instance for the matched operation

**Raises:** `ValueError` — No valid operation config found

**Example:**

```python
from dataclasses import dataclass
from friday_agent_sdk import parse_operation

@dataclass
class CloneConfig:
    operation: str  # Must be "clone"
    repository: str
    branch: str = "main"

@dataclass
class DeployConfig:
    operation: str  # Must be "deploy"
    environment: str
    version: str

OPERATIONS = {
    "clone": CloneConfig,
    "deploy": DeployConfig,
}

config = parse_operation(prompt, OPERATIONS)

match config.operation:
    case "clone":
        # config is typed as CloneConfig
        handle_clone(config)
    case "deploy":
        # config is typed as DeployConfig
        handle_deploy(config)
```

## Extraction strategy

Both functions search in this order:

1. **Balanced-brace JSON objects** — Hand-rolled scanner handles arbitrary nesting
2. **Code-fenced JSON blocks** — Extracts from ` ```json ... ``` `
3. **Full prompt** — Attempts to parse entire prompt as JSON

For `parse_operation()`, only JSON objects containing an `"operation"` field are considered, and the discriminator value selects the schema.

## JSON in markdown

Input may look like:

````markdown
Task: Deploy the application

Here is the configuration:

```json
{ "operation": "deploy", "environment": "production", "version": "1.2.3" }
```
````

Additional context about the deployment...

````

Both `parse_input()` and `parse_operation()` extract the JSON block correctly.

## Dataclass validation

When using a schema:

- Only fields defined in the dataclass are extracted (unknown keys filtered)
- Missing required fields raise `ValueError` with clear message
- Type hints are not enforced at runtime (Python limitation)

```python
@dataclass
class StrictConfig:
    required_field: str
    optional_field: int = 0

# Raises: ValueError: missing {'required_field'}
config = parse_input('{"optional_field": 5}', StrictConfig)

# Succeeds: required_field="value", optional_field=5
config = parse_input(
    '{"required_field": "value", "optional_field": 5, "extra": "ignored"}',
    StrictConfig,
)
````

## Error messages

Clear errors for debugging:

```python
# No JSON found
parse_input("Just text without JSON")
# ValueError: No valid JSON object found in prompt. Prompt starts with: Just text...

# Invalid JSON
parse_input("{invalid json}")
# ValueError: No valid JSON object found...

# Schema mismatch
parse_input('{"wrong": "fields"}', Config)
# ValueError: JSON parsed but doesn't match Config: missing {'repository'}

# Operation not found
parse_operation('{"operation": "unknown"}', {"clone": CloneConfig})
# ValueError: No valid operation config found. Known operations: ['clone']...
```

## Real example: Jira agent

```python
from dataclasses import dataclass
from friday_agent_sdk import agent, err, ok, parse_operation

@dataclass
class IssueViewConfig:
    operation: str
    issue_key: str

@dataclass
class IssueSearchConfig:
    operation: str
    jql: str
    max_results: int = 50

@dataclass
class IssueCreateConfig:
    operation: str
    project_key: str
    summary: str
    description: str | None = None
    issue_type: str = "Bug"

OPERATIONS = {
    "issue-view": IssueViewConfig,
    "issue-search": IssueSearchConfig,
    "issue-create": IssueCreateConfig,
}

@agent(id="jira", version="1.0.0", description="Jira operations")
def execute(prompt, ctx):
    try:
        config = parse_operation(prompt, OPERATIONS)
    except ValueError as e:
        return err(str(e))

    match config.operation:
        case "issue-view":
            return handle_view(config, ctx)
        case "issue-search":
            return handle_search(config, ctx)
        case "issue-create":
            return handle_create(config, ctx)
        case _:
            return err(f"Unknown operation: {config.operation}")
```

## When to use

| Function                           | Use When                                                   |
| ---------------------------------- | ---------------------------------------------------------- |
| `parse_input(prompt)`              | Single configuration, flexible parsing, no operation types |
| `parse_input(prompt, Schema)`      | Single configuration, want typed fields                    |
| `parse_operation(prompt, schemas)` | Multiple operations, discriminated by `"operation"` field  |

## Implementation details

The balanced-brace scanner:

- Handles arbitrary nesting depth (recursive objects/arrays)
- Tracks string boundaries and escape sequences
- Avoids miscounting braces inside string literals
- Returns all valid JSON objects found, tries each in order

This hand-rolled approach is necessary because regex cannot handle arbitrary nesting depth reliably.

## See also

- [How to Handle Structured Input](../how-to/handle-structured-input.md) — Task-oriented guide
- [Jira agent example](../../examples/jira-agent/agent.py) — Full operation dispatch
