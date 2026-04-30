"""LLM + HTTP agent — exercises ctx.llm.generate() and ctx.http.fetch().

Prompt prefix selects which capability and success/error path to exercise.
"""

from friday_agent_sdk import HttpError, LlmError, agent, err, ok, run


@agent(
    id="llm-http-agent",
    version="1.0.0",
    description="Exercises LLM and HTTP capabilities",
)
def execute(prompt, ctx):
    if prompt.startswith("llm:"):
        return _handle_llm(prompt[4:], ctx)
    elif prompt.startswith("llm-fail:"):
        return _handle_llm_fail(prompt[9:], ctx)
    elif prompt.startswith("http:"):
        return _handle_http(prompt[5:], ctx)
    elif prompt.startswith("http-fail:"):
        return _handle_http_fail(prompt[10:], ctx)
    else:
        return err(f"unknown prefix in prompt: {prompt}")


def _handle_llm(user_msg, ctx):
    """LLM success path — model 'test-model' expected to succeed."""
    response = ctx.llm.generate(
        messages=[{"role": "user", "content": user_msg}],
        model="test-model",
    )
    return ok(
        {
            "llm_result": {
                "text": response.text,
                "model": response.model,
                "finish_reason": response.finish_reason,
            }
        }
    )


def _handle_llm_fail(user_msg, ctx):
    """LLM error path — model 'fail-model' triggers LlmError."""
    try:
        ctx.llm.generate(
            messages=[{"role": "user", "content": user_msg}],
            model="fail-model",
        )
        return err("expected LlmError but got success")
    except LlmError as e:
        return err(str(e))


def _handle_http(path, ctx):
    """HTTP success path — example.com expected to resolve."""
    response = ctx.http.fetch(
        f"https://example.com/{path}",
        method="GET",
    )
    return ok(
        {
            "http_result": {
                "status": response.status,
                "body": response.body,
            }
        }
    )


def _handle_http_fail(path, ctx):
    """HTTP error path — fail.example.com triggers HttpError."""
    try:
        ctx.http.fetch(
            f"https://fail.example.com/{path}",
            method="GET",
        )
        return err("expected HttpError but got success")
    except HttpError as e:
        return err(str(e))


if __name__ == "__main__":
    run()
