"""Time agent — fixture for MCP tool usage with mcp-server-time.

Exercises ctx.tools.list() and ctx.tools.call() against a real MCP server
that provides get_current_time and convert_time tools.
"""

from friday_agent_sdk import ToolCallError, agent, err, ok
from friday_agent_sdk._bridge import Agent  # noqa: F401 — componentize-py needs this


@agent(
    id="time-agent",
    version="1.0.0",
    description="Exercises real MCP tool usage with time server",
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
    if prompt == "discover":
        return _handle_discover(ctx)
    elif prompt == "now":
        return _handle_now(ctx)
    elif prompt.startswith("convert "):
        return _handle_convert(prompt, ctx)
    elif prompt == "combo":
        return _handle_combo(ctx)
    elif prompt == "bad-tool":
        return _handle_bad_tool(ctx)
    elif prompt == "bad-tool-then-now":
        return _handle_bad_tool_then_now(ctx)
    else:
        return err(f"unknown prompt: {prompt}")


def _handle_discover(ctx):
    # MCP tool discovery — introspects what mcp-server-time provides
    tools = ctx.tools.list()
    return ok({"tools": [t.name for t in tools], "count": len(tools)})


def _handle_now(ctx):
    result = ctx.tools.call("get_current_time", {"timezone": "UTC"})
    return ok({"time_result": result})


def _handle_convert(prompt, ctx):
    """Parse 'convert <time> <from_tz> <to_tz>' and convert."""
    parts = prompt.split()
    if len(parts) != 4:
        return err("expected: convert <HH:MM> <source_tz> <target_tz>")
    _, time_str, source_tz, target_tz = parts
    result = ctx.tools.call(
        "convert_time",
        {
            "source_timezone": source_tz,
            "time": time_str,
            "target_timezone": target_tz,
        },
    )
    return ok({"convert_result": result})


def _handle_combo(ctx):
    # Sequential tool calls verify ctx.tools state persists across invocations
    time_result = ctx.tools.call("get_current_time", {"timezone": "UTC"})
    convert_result = ctx.tools.call(
        "convert_time",
        {
            "source_timezone": "UTC",
            "time": "12:00",
            "target_timezone": "America/New_York",
        },
    )
    return ok({"time_result": time_result, "convert_result": convert_result})


def _handle_bad_tool(ctx):
    """Call a nonexistent tool — should raise ToolCallError."""
    try:
        ctx.tools.call("nonexistent_tool", {})
        return err("expected ToolCallError but got success")
    except ToolCallError as e:
        return err(str(e))


def _handle_bad_tool_then_now(ctx):
    # Error recovery pattern — failed tool call should not break subsequent calls
    try:
        ctx.tools.call("nonexistent_tool", {})
        return err("expected ToolCallError but got success")
    except ToolCallError as e:
        error_msg = str(e)

    result = ctx.tools.call("get_current_time", {"timezone": "UTC"})
    return ok({"error_caught": error_msg, "time_result": result})
