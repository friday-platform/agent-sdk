"""Bash tool agent — fixture for bash tool capability testing.

Exercises bash tool capabilities to verify:
- stdout/stderr capture (echo)
- Exit code propagation (exit-code)
- Working directory isolation (cwd)
- Environment variable injection (env)
- Multi-command sequences (clone)
"""

from friday_agent_sdk import agent, err, ok, parse_input, run


@agent(id="bash-test", version="1.0.0", description="Exercises bash tool capabilities")
def execute(prompt, ctx):
    cmd = parse_input(prompt)
    action = cmd.get("action", "echo")

    if action == "dump-prompt":
        return ok({"raw_prompt": prompt[:2000]})

    if action == "list-tools":
        tools = ctx.tools.list()
        return ok({"tools": [t.name for t in tools]})

    if action == "echo":
        result = ctx.tools.call("bash", {"command": "echo hello"})
        return ok({"bash_result": result})

    if action == "exit-code":
        result = ctx.tools.call("bash", {"command": "exit 42"})
        return ok({"bash_result": result})

    if action == "cwd":
        result = ctx.tools.call("bash", {"command": "pwd", "cwd": "/tmp"})
        return ok({"bash_result": result})

    if action == "env":
        result = ctx.tools.call(
            "bash",
            {
                "command": "echo $QA_TEST_VAR",
                "env": {"QA_TEST_VAR": "host-bridge-works"},
            },
        )
        return ok({"bash_result": result})

    if action == "clone":
        repo_url = cmd["repo_url"]
        result = ctx.tools.call(
            "bash",
            {"command": (f"git clone --depth 1 {repo_url} /tmp/qa-bash-clone-test && ls /tmp/qa-bash-clone-test")},
        )
        ctx.tools.call("bash", {"command": "rm -rf /tmp/qa-bash-clone-test"})
        return ok({"bash_result": result})

    return err(f"Unknown action: {action}")


if __name__ == "__main__":
    run()
