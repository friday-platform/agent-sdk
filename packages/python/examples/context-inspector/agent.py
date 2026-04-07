"""Context inspector agent — returns all context fields for E2E verification.

Serializes every field from AgentContext so tests can assert that env,
config, session, output_schema, and tools all survive the host-to-WASM
round trip.
"""

import json

from friday_agent_sdk import agent, ok
from friday_agent_sdk._bridge import Agent  # noqa: F401 — componentize-py needs this


@agent(
    id="context-inspector",
    version="1.0.0",
    description="Returns all context fields for verification",
)
def execute(prompt, ctx):
    return ok(
        json.dumps(
            {
                "prompt": prompt,
                "env": ctx.env,
                "config": ctx.config,
                "session": {
                    "id": ctx.session.id,
                    "workspace_id": ctx.session.workspace_id,
                    "user_id": ctx.session.user_id,
                    "datetime": ctx.session.datetime,
                }
                if ctx.session
                else None,
                "output_schema": ctx.output_schema,
                "has_tools": ctx.tools is not None,
                "tool_count": len(ctx.tools.list()) if ctx.tools else 0,
            }
        )
    )
