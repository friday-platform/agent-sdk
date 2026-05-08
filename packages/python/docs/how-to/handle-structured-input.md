# How to Handle Structured Input

Use `ctx.input` for runtime-provided action input, especially workspace-job `inputFrom` handoffs. Use `parse_input()` and `parse_operation()` only when you need to extract JSON from the human-readable prompt.

> **New here?** See [Your First Friday Agent](../tutorial/your-first-agent.md#step-3-build-and-test) for how to build and run your agent.

## Action input from workspace jobs

Friday can pass structured action input separately from the rendered prompt. This is the preferred API for multi-step jobs because upstream outputs may be compacted into summary + artifact refs instead of being inlined.

```python
from friday_agent_sdk import agent, ok

@agent(id="email-classifier", version="1.0.0", description="Classifies fetched emails")
def execute(prompt, ctx):
    fetched = ctx.input.get("fetched-emails")  # compact summary/ref payload
    refs = ctx.input.artifact_refs("fetched-emails")

    payload = ctx.input.artifact_json("fetched-emails")
    emails = payload.get("emails", [])

    return ok({
        "count": len(emails),
        "artifactIds": [ref.id for ref in refs],
    })
```

Use this pattern when a workspace job chains steps with `outputTo` → `inputFrom`. The downstream worker dereferences the artifact only inside its own execution; job results, chat supervisor context, and persisted documents can remain compact.

## Prompt JSON extraction

Friday also sends your agent an "enriched prompt" — a markdown string containing:

- The user's task
- Temporal facts (current time, relevant history)
- Signal data (HTTP request body, cron metadata)
- Accumulated context from previous steps

Deterministic code agents cannot parse this like LLMs do. The SDK provides extraction utilities.

## Simple JSON extraction

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

## Extraction strategy

`parse_input()` searches in this order:

1. **Raw JSON objects** — Scans for balanced-brace JSON objects
2. **Code-fenced blocks** — Extracts from ` ```json ... ``` `
3. **Full prompt** — Attempts to parse the entire prompt as JSON

When you use a dataclass schema, unknown keys are filtered out so extra context in the prompt doesn't break object construction.

## Discriminated operations

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

## Plain dict extraction

Without a dataclass, get a plain dict:

```python
# Returns dict
data = parse_input(prompt)

# Access fields
task = data.get("task")
priority = data.get("priority", "medium")
```

## Validation errors

When using dataclasses, missing required fields produce clear errors:

```python
@dataclass
class StrictConfig:
    required_field: str
    another_required: int

config = parse_input('{"required_field": "value"}', StrictConfig)
# Raises: ValueError: JSON parsed but doesn't match StrictConfig: missing {'another_required'}
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

## When to use which

| Function                           | Use When                                                            |
| ---------------------------------- | ------------------------------------------------------------------- |
| `ctx.input.get(name)`              | Read a named runtime action input / `inputFrom` payload             |
| `ctx.input.artifact_refs(name)`    | Inspect artifact refs attached to a compact input payload           |
| `ctx.input.artifact_json(name)`    | Hydrate JSON artifact contents through host `artifacts_get`         |
| `parse_input(prompt)`              | Single prompt-embedded JSON configuration, no discriminated types   |
| `parse_input(prompt, Schema)`      | Single prompt-embedded JSON configuration with typed validation     |
| `parse_operation(prompt, schemas)` | Multiple prompt-embedded operations via `"operation"` discriminator |

## Tips

- Include `"operation"` field in JSON for discriminated parsing
- Use dataclasses for compile-time type safety and clear error messages
- Provide default values for optional fields
- Handle `ValueError` from parsing with graceful error returns

## See also

- [API reference: parse utilities](../reference/parse-utilities.md)
- [Jira agent example](../../examples/jira-agent/agent.py) — Full operation dispatch
