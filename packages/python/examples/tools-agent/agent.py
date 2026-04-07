"""Tools agent — fixture for async host function round-trip testing.

Exercises all four capabilities imports: callTool, listTools, log, streamEmit.
"""

import json

from friday_agent_sdk import ToolCallError, agent, err, ok
from friday_agent_sdk._bridge import Agent  # noqa: F401 — componentize-py needs this


@agent(id="tools-agent", version="1.0.0", description="Exercises host capabilities")
def execute(prompt, ctx):
    # Log that we started
    from wit_world.imports.capabilities import log, stream_emit

    log(1, f"tools-agent executing: {prompt}")

    # Emit a stream event
    stream_emit("started", json.dumps({"prompt": prompt}))

    # List available tools
    tools = ctx.tools.list()
    tool_count = len(tools)

    # Error path: if prompt starts with "fail:", call a tool named "fail"
    if prompt.startswith("fail:"):
        try:
            ctx.tools.call("fail", {"reason": prompt[5:]})
            return err("expected ToolCallError but got success")
        except ToolCallError as e:
            return err(str(e))

    # Success path: call the echo tool
    result = ctx.tools.call("echo", {"msg": prompt})

    stream_emit("completed", json.dumps({"tool_count": tool_count}))

    return ok({"tool_result": result, "tool_count": tool_count})
