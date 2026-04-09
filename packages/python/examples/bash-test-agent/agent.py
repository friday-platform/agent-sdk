"""Bash tool agent — fixture for bash tool WASM bridge testing.

Exercises bash tool capabilities across the WASM boundary to verify:
- stdout/stderr capture (echo)
- Exit code propagation (exit-code)
- Working directory isolation (cwd)  
- Environment variable injection (env)
- Multi-command sequences (clone)
"""

from friday_agent_sdk import agent, err, ok, parse_input
from friday_agent_sdk._bridge import Agent  # noqa: F401 — componentize-py needs this


@agent(id="bash-test", version="1.0.0", description="Exercises bash tool through WASM")
def execute(prompt, ctx):
    cmd = parse_input(prompt)
    action = cmd.get("action", "echo")

    if action == "dump-prompt":
        return ok({"raw_prompt": prompt[:2000]})

    if action == "list-tools":
        tools = ctx.tools.list()
        return ok({"tools": [t.name for t in tools]})

    if action == "echo":
        # Verify stdout capture across WASM boundary
        result = ctx.tools.call("bash", {"command": "echo hello"})
        return ok({"bash_result": result})

    if action == "exit-code":
        # Verify non-zero exit codes propagate correctly (42 chosen as test value)
        result = ctx.tools.call("bash", {"command": "exit 42"})
        return ok({"bash_result": result})

    if action == "cwd":
        # Verify working directory isolation (runs in /tmp, not agent's cwd)
        result = ctx.tools.call("bash", {"command": "pwd", "cwd": "/tmp"})
        return ok({"bash_result": result})

    if action == "env":
        # Verify environment variable injection through WASM boundary
        result = ctx.tools.call(
            "bash",
            {
                "command": "echo $QA_TEST_VAR",
                "env": {"QA_TEST_VAR": "wasm-bridge-works"},
            },
        )
        return ok({"bash_result": result})

    if action == "clone":
        # Multi-command sequence with cleanup — tests stateful bash sessions
        repo_url = cmd["repo_url"]
        result = ctx.tools.call(
            "bash",
            {
                "command": (
                    f"git clone --depth 1 {repo_url}"
                    " /tmp/qa-bash-clone-test"
                    " && ls /tmp/qa-bash-clone-test"
                )
            },
        )
        # Cleanup runs as separate call — tests independent command execution
        ctx.tools.call("bash", {"command": "rm -rf /tmp/qa-bash-clone-test"})
        return ok({"bash_result": result})

    return err(f"Unknown action: {action}")
