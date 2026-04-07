# ctx.tools

MCP tool capability wrapper for invoking Model Context Protocol servers.

## Class: Tools

```python
class Tools:
    def list(self) -> list[ToolDefinition]: ...
    def call(self, name: str, args: dict) -> dict: ...
```

## Methods

### list()

List all available tools from configured MCP servers.

**Returns:** `list[ToolDefinition]`

**Example:**

```python
tools = ctx.tools.list()

for tool in tools:
    print(f"{tool.name}: {tool.description}")
    print(f"  Schema: {tool.input_schema}")
```

### call()

Call a tool by name with arguments.

**Parameters:**

| Parameter | Type   | Required | Description                            |
| --------- | ------ | -------- | -------------------------------------- |
| `name`    | `str`  | Yes      | Tool identifier                        |
| `args`    | `dict` | Yes      | Arguments matching tool's input schema |

**Returns:** `dict` — Tool output parsed from JSON

**Raises:** `ToolCallError` on tool execution failure

**Example:**

```python
# Call with typed arguments
result = ctx.tools.call(
    "search_issues",
    {
        "query": "is:open label:bug",
        "repo": "my-org/my-repo",
    },
)

# Access result fields
issues = result["issues"]
count = result["count"]
```

## ToolDefinition

```python
@dataclass
class ToolDefinition:
    name: str           # Tool identifier (unique within server)
    description: str    # Human-readable description
    input_schema: dict  # JSON Schema for arguments
```

## Configuration

MCP servers are configured in the `@agent` decorator:

```python
@agent(
    id="github-helper",
    version="1.0.0",
    description="Uses GitHub",
    mcp={
        "github": {
            "transport": {
                "type": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
                "env": {
                    "GITHUB_TOKEN": "{{env.GITHUB_TOKEN}}",
                },
            }
        }
    },
)
def execute(prompt, ctx):
    # ctx.tools.list() includes tools from github server
    result = ctx.tools.call("search_issues", {...})
    ...
```

## Error Handling

```python
from friday_agent_sdk import ToolCallError, agent, err, ok

@agent(id="safe-caller", version="1.0.0", description="Handles tool errors")
def execute(prompt, ctx):
    try:
        result = ctx.tools.call("risky_operation", {"data": prompt})
    except ToolCallError as e:
        return err(f"Tool failed: {e}")

    return ok({"result": result})
```

## Finding Tools

Filter by name pattern:

```python
tools = ctx.tools.list()
search_tools = [t for t in tools if "search" in t.name]
git_tools = [t for t in tools if t.name.startswith("git")]
```

## Dynamic Tool Selection

```python
def execute(prompt, ctx):
    tools = ctx.tools.list()

    # Find appropriate tool based on prompt
    if "issue" in prompt.lower():
        tool = next((t for t in tools if "issue" in t.name), None)
    elif "pr" in prompt.lower() or "pull" in prompt.lower():
        tool = next((t for t in tools if "pull" in t.name), None)
    else:
        return err("No appropriate tool found")

    if not tool:
        available = [t.name for t in tools]
        return err(f"Tool not found. Available: {available}")

    result = ctx.tools.call(tool.name, {"query": prompt})
    return ok({"result": result})
```

## Real Example: Time Operations

```python
@agent(
    id="time-agent",
    version="1.0.0",
    description="Time conversion",
    mcp={
        "time": {
            "transport": {
                "type": "stdio",
                "command": "uvx",
                "args": ["mcp-server-time", "--local-timezone", "UTC"],
            }
        }
    },
)
def execute(prompt, ctx):
    # Discover available tools
    tools = ctx.tools.list()
    tool_names = [t.name for t in tools]

    # Call current time
    now = ctx.tools.call("get_current_time", {"timezone": "UTC"})

    # Convert time
    converted = ctx.tools.call(
        "convert_time",
        {
            "source_timezone": "UTC",
            "time": "14:30",
            "target_timezone": "America/New_York",
        },
    )

    return ok({
        "current_utc": now,
        "converted": converted,
        "available_tools": tool_names,
    })
```

## Multiple MCP Servers

Tools from all configured servers are merged into a single namespace:

```python
@agent(
    id="multi",
    version="1.0.0",
    mcp={
        "github": {...},
        "postgres": {...},
    },
)
def execute(prompt, ctx):
    all_tools = ctx.tools.list()
    # Contains tools from both github and postgres servers
    github_count = len([t for t in all_tools if "github" in t.name])
    db_count = len([t for t in all_tools if "sql" in t.name])
    ...
```

## Tool Chaining

```python
def execute(prompt, ctx):
    # Step 1: Search
    search_result = ctx.tools.call(
        "search_issues",
        {"query": prompt},
    )

    # Step 2: Get details for top result
    top_issue = search_result["issues"][0]
    details = ctx.tools.call(
        "get_issue",
        {
            "owner": "my-org",
            "repo": "my-repo",
            "issue_number": top_issue["number"],
        },
    )

    # Step 3: Add comment
    ctx.tools.call(
        "add_issue_comment",
        {
            "owner": "my-org",
            "repo": "my-repo",
            "issue_number": top_issue["number"],
            "body": "Analysing this issue now...",
        },
    )

    return ok({"analysed": top_issue["title"]})
```

## Schema Inspection

```python
tool = next(t for t in ctx.tools.list() if t.name == "create_issue")

# Inspect required fields
schema = tool.input_schema
required = schema.get("required", [])
properties = schema.get("properties", {})

for field in required:
    print(f"Required: {field} ({properties[field].get('type')})")
```

## Common MCP Servers

| Server     | Package                                   | Tools                                                     |
| ---------- | ----------------------------------------- | --------------------------------------------------------- |
| GitHub     | `@modelcontextprotocol/server-github`     | search_issues, get_issue, create_issue, add_comment, etc. |
| PostgreSQL | `@modelcontextprotocol/server-postgres`   | query, list_tables, describe_table                        |
| Time       | `mcp-server-time`                         | get_current_time, convert_time                            |
| Filesystem | `@modelcontextprotocol/server-filesystem` | read_file, write_file, list_directory                     |
| Fetch      | `@modelcontextprotocol/server-fetch`      | fetch (HTTP requests)                                     |

## Transport Types

Currently supported: `stdio`

Planned: `sse` (Server-Sent Events)

## Environment Variables

Reference agent environment in MCP server env:

```python
mcp={
    "github": {
        "transport": {
            "type": "stdio",
            "command": "npx",
            "args": ["..."],
            "env": {
                # References ctx.env["GITHUB_TOKEN"]
                "GITHUB_TOKEN": "{{env.GITHUB_TOKEN}}",
            }
        }
    }
}
```

Or configure agent environment separately:

```python
@agent(
    ...,
    environment={
        "required": [
            {"name": "GITHUB_TOKEN", "description": "GitHub API token"},
        ]
    },
)
```

## See Also

- [How to Use MCP Tools](../how-to/use-mcp-tools.md) — Task-oriented guide
- [MCP specification](https://modelcontextprotocol.io/)
- [MCP servers registry](https://github.com/modelcontextprotocol/servers)
