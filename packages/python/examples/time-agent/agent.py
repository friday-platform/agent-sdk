"""Time agent — exercises MCP tool usage with mcp-server-time."""

import contextlib

from friday_agent_sdk import ToolCallError, agent, err, ok, run


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
    tools = ctx.tools.list()
    return ok({"tool_names": [t.name for t in tools]})


def _handle_now(ctx):
    result = ctx.tools.call("get_current_time", {"timezone": "UTC"})
    return ok({"utc_now": result})


def _handle_convert(prompt, ctx):
    parts = prompt.split(" ", 2)
    if len(parts) < 3:
        return err("Usage: convert <time> <from> to <to>")
    _, time_str, rest = parts
    from_to = rest.split(" to ")
    if len(from_to) != 2:
        return err("Usage: convert <time> <from> to <to>")
    result = ctx.tools.call(
        "convert_time",
        {
            "source_timezone": from_to[0].strip(),
            "time": time_str,
            "target_timezone": from_to[1].strip(),
        },
    )
    return ok({"converted": result})


def _handle_combo(ctx):
    now = ctx.tools.call("get_current_time", {"timezone": "UTC"})
    converted = ctx.tools.call(
        "convert_time",
        {
            "source_timezone": "UTC",
            "time": now["time"],
            "target_timezone": "America/New_York",
        },
    )
    return ok({"utc": now, "nyc": converted})


def _handle_bad_tool(ctx):
    try:
        ctx.tools.call("nonexistent_tool", {})
        return err("expected ToolCallError")
    except ToolCallError as e:
        return ok({"error": str(e)})


def _handle_bad_tool_then_now(ctx):
    with contextlib.suppress(ToolCallError):
        ctx.tools.call("nonexistent_tool", {})
    result = ctx.tools.call("get_current_time", {"timezone": "UTC"})
    return ok({"recovered": True, "utc_now": result})


if __name__ == "__main__":
    run()
