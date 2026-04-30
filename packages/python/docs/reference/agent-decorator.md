# @agent Decorator

Registers a function as a Friday agent with metadata for discovery and execution.

## Signature

```python
@agent(
    *,
    id: str,
    version: str,
    description: str,
    display_name: str | None = None,
    summary: str | None = None,
    constraints: str | None = None,
    examples: list[str] | None = None,
    input_schema: type | None = None,
    output_schema: type | None = None,
    environment: dict[str, Any] | None = None,
    mcp: dict[str, Any] | None = None,
    llm: dict[str, Any] | None = None,
    use_workspace_skills: bool = False,
)
def execute(prompt: str, ctx: AgentContext) -> OkResult | ErrResult:
    ...
```

## Required Parameters

The registration API validates that all three are present. Missing any returns HTTP 400 with `"phase": "validate"`.

### `id`

- **Type:** `str`
- **Description:** Unique identifier for the agent. Use kebab-case.
- **Constraints:** Must be unique within your workspace. Friday prepends `user:` automatically.
- **Example:** `"text-analyzer"`, `"github-helper"`, `"jira-operations"`

### `version`

- **Type:** `str`
- **Description:** Semantic version of the agent.
- **Example:** `"1.0.0"`, `"2.1.0-alpha.1"`
- **Behavior:** Multiple versions coexist on disk; Friday resolves the ID to the highest semver version.

### `description`

- **Type:** `str`
- **Description:** What the agent does. Used by the planner for delegation decisions.
- **Guidance:** Be specific about capabilities and use cases. 50-200 characters.
- **Required:** Registration fails without this field.

## Optional Parameters

### `display_name`

- **Type:** `str | None`
- **Description:** Human-readable name for the UI. Falls back to `id` if not provided.

### `summary`

- **Type:** `str | None`
- **Description:** One-line summary for agent listings.

### `constraints`

- **Type:** `str | None`
- **Description:** Limitations, requirements, or conditions for using the agent.
- **Example:** `"Requires GitHub token. Cannot access workspace database tables."`

### `examples`

- **Type:** `list[str] | None`
- **Description:** Example prompts that trigger this agent. Helps the planner learn delegation patterns.

```python
examples=[
    "Write a Python function to parse JSON",
    "Debug this error in the codebase",
    "Analyze stack traces and identify root causes",
]
```

### `input_schema`

- **Type:** `type | None`
- **Description:** Dataclass type for structured input parsing. Currently informational; used for documentation generation.

### `output_schema`

- **Type:** `type | None`
- **Description:** Dataclass type for structured output. Passed to agent via `ctx.output_schema`.

### `use_workspace_skills`

- **Type:** `bool`
- **Default:** `False`
- **Description:** Whether the agent loads workspace skills before execution.

## Environment Configuration

### `environment`

- **Type:** `dict[str, Any] | None`
- **Description:** Environment variable requirements.

```python
environment={
    "required": [
        {
            "name": "API_KEY",
            "description": "API authentication token",
            "linkRef": {"provider": "anthropic", "key": "api_key"},  # Optional
        },
    ],
    "optional": [
        {
            "name": "DEBUG",
            "description": "Enable debug logging",
        },
    ],
}
```

Access in agent code via `ctx.env["API_KEY"]`.

## MCP Configuration

### `mcp`

- **Type:** `dict[str, Any] | None`
- **Description:** MCP servers to launch alongside the agent.

```python
mcp={
    "github": {
        "transport": {
            "type": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {
                "GITHUB_TOKEN": "{{env.GITHUB_TOKEN}}",  # References ctx.env
            },
        }
    },
    "time": {
        "transport": {
            "type": "stdio",
            "command": "uvx",
            "args": ["mcp-server-time", "--local-timezone", "UTC"],
        }
    },
}
```

## LLM Configuration

### `llm`

- **Type:** `dict[str, Any] | None`
- **Description:** Default LLM provider and model for the agent.

```python
llm={
    "provider": "anthropic",
    "model": "claude-sonnet-4-6",
}
```

Used when `ctx.llm.generate()` is called without explicit model. See [How to Call LLMs](../how-to/call-llms.md) for resolution cascade.

## Handler Function Signature

The decorated function receives:

```python
def execute(prompt: str, ctx: AgentContext) -> OkResult | ErrResult:
    ...
```

### Parameters

- `prompt` — The enriched prompt string from Friday (includes task, context, temporal facts)
- `ctx` — [AgentContext](agent-context.md) with capabilities and metadata

### Return Types

Return either:

- `ok(data)` — Success with structured data
- `ok(data, extras=AgentExtras(...))` — Success with metadata
- `err(message)` — Failure with error message

## Entry Point

Every agent file must end with a `run()` call:

```python
from friday_agent_sdk import agent, ok, run

@agent(id="my-agent", version="1.0.0", description="...")
def execute(prompt, ctx):
    return ok("hello")

if __name__ == "__main__":
    run()
```

`run()` connects to the daemon's message broker, handles the registration or execution handshake, and exits when done. Without it, the agent process spawns and immediately exits.

## Example

```python
from friday_agent_sdk import agent, ok, err, AgentContext, run

@agent(
    id="code-analyzer",
    version="1.2.0",
    description="Analyzes code for bugs, security issues, and style violations",
    summary="Static analysis agent for code review",
    constraints="Requires read access to repository files. Does not execute code.",
    examples=[
        "Analyze this function for security vulnerabilities",
        "Check this code for SQL injection risks",
        "Review this PR for common anti-patterns",
    ],
    environment={
        "required": [
            {"name": "GITHUB_TOKEN", "description": "For accessing private repos"},
        ],
    },
    mcp={
        "github": {
            "transport": {
                "type": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
            }
        }
    },
    llm={"provider": "anthropic", "model": "claude-sonnet-4-6"},
)
def execute(prompt: str, ctx: AgentContext):
    # Implementation
    return ok({"issues": []})

if __name__ == "__main__":
    run()
```

## Registration Validation

The registration pipeline validates metadata against a Zod schema. Validation errors return:

```json
{
  "ok": false,
  "phase": "validate",
  "error": "description is required"
}
```

## Version Semantics

Agent versions follow [Semantic Versioning](https://semver.org/):

- `MAJOR` — Breaking changes to agent behavior
- `MINOR` — New capabilities, backwards compatible
- `PATCH` — Bug fixes, backwards compatible

Friday resolves agent references to the latest semver version:

```bash
# Register v1.0.0
atlas agent register ./my-agent  # version="1.0.0"

# Register v1.0.1
atlas agent register ./my-agent  # version="1.0.1"

# Reference in workspace.yml
agents:
  - id: my-agent    # Resolves to v1.0.1 (latest)
    type: user
```

Both versions remain on disk; rollback is possible by adjusting the workspace reference or re-registering with a downgraded version.

## See Also

- [AgentContext](agent-context.md) — Execution context and capabilities
- [Result types](result-types.md) — `ok()` and `err()` constructors
- [How to Use MCP Tools](../how-to/use-mcp-tools.md)
