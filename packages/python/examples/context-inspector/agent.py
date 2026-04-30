"""Context inspector agent — returns all context fields for E2E verification.

Serializes every field from AgentContext to JSON to verify the host round-trip.
Tests assert that env, config, session, output_schema, and tools all survive
the boundary crossing intact.
"""

import json

from friday_agent_sdk import agent, ok, run


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
                "has_tools": True,
                "tool_count": len(ctx.tools.list()),
            }
        )
    )


if __name__ == "__main__":
    run()
