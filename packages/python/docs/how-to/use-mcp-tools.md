# How to Use MCP Tools

Configure MCP servers in your agent decorator and call tools via `ctx.tools`.

> **New here?** See [Your First Friday Agent](../tutorial/your-first-agent.md#step-3-build-and-test) for how to build and run your agent.

## Configure an MCP Server

Declare required MCP servers in the `@agent` decorator:

```python
from friday_agent_sdk import agent, ok

@agent(
    id="github-helper",
    version="1.0.0",
    description="Uses GitHub MCP server",
    mcp={
        "github": {
            "transport": {
                "type": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
            }
        }
    },
)
def execute(prompt, ctx):
    ...
```

## List Available Tools

```python
tools = ctx.tools.list()

for tool in tools:
    print(f"  {tool.name}: {tool.description}")
    print(f"    Schema: {tool.input_schema}")
```

Returns a list of `ToolDefinition` objects:

```python
tool.name          # Tool identifier
tool.description   # Human-readable description
tool.input_schema  # JSON Schema for arguments
```

## Call a Tool

```python
result = ctx.tools.call(
    "search_issues",
    {
        "query": "is:open label:bug",
        "repo": "my-org/my-repo",
    },
)

# result is a dict parsed from the tool's JSON output
return ok({"issues": result["issues"]})
```

## Error Handling

Tool failures raise `ToolCallError`:

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

## Real Example: Time Operations

```python
@agent(
    id="time-agent",
    version="1.0.0",
    description="Time conversion agent",
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
    # Get current time in Tokyo
    result = ctx.tools.call(
        "get_current_time",
        {"timezone": "Asia/Tokyo"},
    )

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
        "tokyo_time": result,
        "converted": converted,
    })
```

## Multiple MCP Servers

```python
@agent(
    id="multi-tool",
    version="1.0.0",
    description="Uses GitHub and database tools",
    mcp={
        "github": {
            "transport": {
                "type": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
            }
        },
        "postgres": {
            "transport": {
                "type": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-postgres"],
                "env": {
                    "DATABASE_URL": "postgresql://...",
                },
            }
        }
    },
)
def execute(prompt, ctx):
    tools = ctx.tools.list()
    # Tools from both servers are available
    github_tools = [t for t in tools if "github" in t.name]
    db_tools = [t for t in tools if "postgres" in t.name]
    ...
```

## Environment Variables in MCP

Pass environment variables to MCP server processes:

```python
mcp={
    "github": {
        "transport": {
            "type": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {
                "GITHUB_TOKEN": "{{env.GITHUB_TOKEN}}",  # References ctx.env
            }
        }
    }
}
```

Or use the `environment` decorator field for variables your agent accesses:

```python
environment={
    "required": [
        {"name": "GITHUB_TOKEN", "description": "GitHub API token"},
    ]
}
```

## Stdio vs SSE Transport

Currently only `stdio` transport is supported. `sse` (Server-Sent Events) is planned.

## Tool Chaining

```python
# Chain multiple tool calls
tools = ctx.tools.list()

# Find relevant tool by name
search_tool = next((t for t in tools if t.name == "search_issues"), None)
if not search_tool:
    return err("search_issues tool not available")

# Search
issues = ctx.tools.call("search_issues", {"query": prompt})

# For each issue, get details
for issue in issues["issues"][:5]:
    details = ctx.tools.call(
        "get_issue",
        {"owner": "my-org", "repo": "my-repo", "issue_number": issue["number"]},
    )
    # Process details...
```

## See Also

- [API reference: ctx.tools](../reference/tools-capability.md)
- [MCP specification](https://modelcontextprotocol.io/)
- [MCP servers registry](https://github.com/modelcontextprotocol/servers)
