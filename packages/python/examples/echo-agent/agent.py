"""Echo agent — minimal tracer bullet."""

from friday_agent_sdk import agent, ok, run


@agent(id="echo", version="1.0.0", description="Echoes input")
def execute(prompt, ctx):
    return ok(prompt)


if __name__ == "__main__":
    run()
