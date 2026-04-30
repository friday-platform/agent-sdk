"""Tools agent — fixture for capability round-trip testing.

Exercises ctx.tools.list(), ctx.tools.call(), and ctx.stream.progress().
"""

from friday_agent_sdk import ToolCallError, agent, err, ok, run


@agent(id="tools-agent", version="1.0.0", description="Exercises host capabilities")
def execute(prompt, ctx):
    ctx.stream.progress("Starting execution")

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

    ctx.stream.progress("Completed execution")

    return ok({"tool_result": result, "tool_count": tool_count})


if __name__ == "__main__":
    run()
