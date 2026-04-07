"""Echo agent — tracer bullet fixture for WASM pipeline testing.

componentize-py compiles this module. It must:
1. Register the handler via @agent decorator (side-effect import)
2. Export the Agent class that componentize-py expects
"""

from friday_agent_sdk import agent, ok
from friday_agent_sdk._bridge import Agent  # noqa: F401 — componentize-py needs this


@agent(id="echo", version="1.0.0", description="Echoes input")
def execute(prompt, ctx):
    return ok(prompt)
