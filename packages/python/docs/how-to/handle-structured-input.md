# How to Handle Structured Input

Extract JSON configurations from Friday's enriched prompts using `parse_input()` and `parse_operation()`.

> **New here?** See [Your First Friday Agent](../tutorial/your-first-agent.md#step-3-build-and-test) for how to build and run your agent.

## The Problem

Friday sends your agent an "enriched prompt" — a markdown string containing:

- The user's task
- Temporal facts (current time, relevant history)
- Signal data (HTTP request body, cron metadata)
- Accumulated context from previous steps

Deterministic code agents cannot parse this like LLMs do. The SDK provides extraction utilities.

## Simple JSON Extraction

Use `parse_input()` to extract a JSON object from the prompt:

```python
from dataclasses import dataclass
from friday_agent_sdk import agent, ok, parse_input

@dataclass
class Config:
    repository: str
    branch: str
    dry_run: bool = False

@agent(id="git-agent", version="1.0.0", description="Git operations")
def execute(prompt, ctx):
    # Extracts JSON and validates against Config dataclass
    config = parse_input(prompt, Config)

    # config.repository, config.branch, config.dry_run available
    return ok({
        "repo": config.repository,
        "branch": config.branch,
    })
```

The prompt might contain:

````markdown
Task: Deploy the application

```json
{ "repository": "my-org/app", "branch": "main", "dry_run": true }
```
````

## Extraction Strategy

`parse_input()` searches in this order:

1. **Raw JSON objects** — Scans for balanced-brace JSON objects
2. **Code-fenced blocks** — Extracts from ` ```json ... ``` `
3. **Full prompt** — Attempts to parse the entire prompt as JSON

Unknown keys are filtered when using a dataclass schema, preventing enrichment context from crashing construction.

## Discriminated Operations

When your agent handles multiple operations, use `parse_operation()`:

```python
from dataclasses import dataclass
from friday_agent_sdk import agent, err, ok, parse_operation

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

@agent(id="ops-agent", version="1.0.0", description="Git operations")
def execute(prompt, ctx):
    try:
        config = parse_operation(prompt, OPERATIONS)
    except ValueError as e:
        return err(f"Invalid operation: {e}")

    match config.operation:
        case "clone":
            return _handle_clone(config)
        case "deploy":
            return _handle_deploy(config)
        case _:
            return err(f"Unknown operation: {config.operation}")
```

## Plain Dict Extraction

Without a dataclass, get a plain dict:

```python
# Returns dict
data = parse_input(prompt)

# Access fields
task = data.get("task")
priority = data.get("priority", "medium")
```

## Validation Errors

When using dataclasses, missing required fields produce clear errors:

```python
@dataclass
class StrictConfig:
    required_field: str
    another_required: int

config = parse_input('{"required_field": "value"}', StrictConfig)
# Raises: ValueError: JSON parsed but doesn't match StrictConfig: missing {'another_required'}
```

## Real Example: Jira Agent

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

OPERATION_SCHEMAS = {
    "issue-view": IssueViewConfig,
    "issue-search": IssueSearchConfig,
    "issue-create": IssueCreateConfig,
}

@agent(id="jira", version="1.0.0", description="Jira operations")
def execute(prompt, ctx):
    try:
        config = parse_operation(prompt, OPERATION_SCHEMAS)
    except ValueError as e:
        return err(str(e))

    match config.operation:
        case "issue-view":
            return _view_issue(config, ctx)
        case "issue-search":
            return _search_issues(config, ctx)
        case "issue-create":
            return _create_issue(config, ctx)
```

## When to Use Which

| Function                           | Use When                                            |
| ---------------------------------- | --------------------------------------------------- |
| `parse_input(prompt)`              | Single configuration, no discriminated types        |
| `parse_input(prompt, Schema)`      | Single configuration, want typed validation         |
| `parse_operation(prompt, schemas)` | Multiple operations via `"operation"` discriminator |

## Tips

- Include `"operation"` field in JSON for discriminated parsing
- Use dataclasses for compile-time type safety and clear error messages
- Provide default values for optional fields
- Handle `ValueError` from parsing with graceful error returns

## See Also

- [API reference: parse utilities](../reference/parse-utilities.md)
- [Jira agent example](../../examples/jira-agent/agent.py) — Full operation dispatch
