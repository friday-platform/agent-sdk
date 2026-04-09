"""Tools agent — fixture for async host function round-trip testing.

Exercises all four capabilities imports: callTool, listTools, log, streamEmit.
"""

import json

from friday_agent_sdk import ToolCallError, agent, err, ok
from friday_agent_sdk._bridge import Agent  # noqa: F401 — componentize-py needs this


@agent(id="tools-agent", version="1.0.0", description="Exercises host capabilities")
def execute(prompt, ctx):
    # Host capabilities: log levels 1-5, stream events, tools
    from wit_world.imports.capabilities import log, stream_emit

    # Log level 1 = debug; 5 = critical. Using 1 for routine execution tracing.
    log(1, f"tools-agent executing: {prompt}")

    # Stream events for real-time progress — consumed by host's progress UI
    stream_emit("started", json.dumps({"prompt": prompt}))

    tools = ctx.tools.list()
    tool_count = len(tools)

    # Test error propagation — fail: prefix triggers ToolCallError
    if prompt.startswith("fail:"):
        try:
            ctx.tools.call("fail", {"reason": prompt[5:]})
            return err("expected ToolCallError but got success")
        except ToolCallError as e:
            return err(str(e))

    result = ctx.tools.call("echo", {"msg": prompt})

    stream_emit("completed", json.dumps({"tool_count": tool_count}))

    return ok({"tool_result": result, "tool_count": tool_count})
