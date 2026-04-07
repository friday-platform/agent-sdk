"""Claude Code agent — autonomous coding via Claude Code provider.

Port of packages/bundled-agents/src/claude-code/agent.ts to Python.
Routes claude-code execution through the host's LLM provider abstraction,
with the host managing subprocess lifecycle and sandbox.
"""

import json

from friday_agent_sdk import AgentExtras, ArtifactRef, agent, err, ok
from friday_agent_sdk._bridge import Agent  # noqa: F401 — componentize-py needs this
from friday_agent_sdk._result import ErrResult, OkResult

# ---------------------------------------------------------------------------
# Pre-processing
# ---------------------------------------------------------------------------

_EXTRACTION_PROMPT = """\
Extract repository, task, and effort level from this prompt.

If the prompt instructs cloning a repository:
- Extract the repo in "owner/repo" format (not a full URL)
- Remove the cloning instruction from the task
- Return the rest of the task verbatim

If no cloning is mentioned: repo is null and task is the original prompt verbatim.

Classify effort:
- low: reading files, explaining code, answering questions, simple queries
- medium: focused edits, single-file changes, small bug fixes, adding tests
- high: multi-file refactors, complex debugging, architecture changes, large features

Prompt:
"""

_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "repo": {
            "type": ["string", "null"],
            "description": (
                "Repository in owner/repo format, or null if no clone instruction"
            ),
        },
        "task": {
            "type": "string",
            "description": (
                "Task with clone instruction removed, or original prompt verbatim"
            ),
        },
        "effort": {
            "type": "string",
            "enum": ["low", "medium", "high"],
            "description": (
                "Task complexity: low=read/query/explain, "
                "medium=focused edits/single-file changes, "
                "high=multi-file refactors/debugging/complex architecture"
            ),
        },
    },
    "required": ["repo", "task", "effort"],
}

_SYSTEM_APPEND_BASE = (
    "You have authenticated access to the gh CLI for GitHub operations. "
    "Use it for cloning repos, creating PRs, managing issues, and "
    "interacting with GitHub APIs. Return summary of actions. "
    "Concise, factual, markdown."
)


def _select_model(effort: str) -> tuple[str, str]:
    """Map effort to (claude-code provider model ID, fallback model ID)."""
    if effort == "high":
        return ("claude-code:claude-opus-4-6", "claude-sonnet-4-6")
    return ("claude-code:claude-sonnet-4-6", "claude-haiku-4-5")


def _build_system_append(skills: list[dict] | None) -> str:
    if not skills:
        return _SYSTEM_APPEND_BASE
    names = ", ".join(f'"{s["name"]}"' for s in skills)
    return (
        f"{_SYSTEM_APPEND_BASE}\n\n"
        f"IMPORTANT: Before starting work, load the following workspace "
        f"skills using the Skill tool: {names}. "
        f"These skills define your behavior for this task."
    )


def _parse_structured_output(text: str) -> dict | None:
    """Parse JSON from response text, validating it's a dict (not array/string)."""
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        return None
    except (json.JSONDecodeError, TypeError):
        return None


def _create_artifact(ctx, prompt: str, data: str) -> ArtifactRef | None:
    """Create a platform artifact to persist the output. Returns ref or None."""
    try:
        response = ctx.http.fetch(
            f"{ctx.config.get('platformUrl', 'http://localhost:8080')}/api/artifacts",
            method="POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps(
                {
                    "data": {
                        "type": "summary",
                        "version": 1,
                        "data": data,
                    },
                    "title": "Claude Code Output",
                    "summary": (
                        f"Claude Code: {prompt[:100]}"
                        f"{'...' if len(prompt) > 100 else ''}"
                    ),
                }
            ),
        )
        if response.status < 400:
            result = response.json()
            artifact = result.get("artifact", {})
            return ArtifactRef(
                id=artifact.get("id", ""),
                type=artifact.get("type", ""),
                summary=artifact.get("summary", ""),
            )
    except Exception:
        pass  # Artifact creation is best-effort
    return None


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


@agent(
    id="claude-code",
    version="1.0.0",
    display_name="Claude Code",
    description=(
        "Execute coding tasks in a sandboxed environment via Claude Code SDK. "
        "Clones repos, reads/writes files, runs commands, analyzes codebases, "
        "and debugs issues. USE FOR: code generation, code changes, codebase "
        "analysis, debugging, root cause analysis."
    ),
    constraints=(
        "Runs in isolated sandbox. Requires Anthropic API key and GitHub "
        "token. Cannot access workspace resource tables or artifacts directly. "
        "For reading GitHub data (PRs, issues, commits, repos), use the "
        "github MCP server. For data analysis, use data-analyst."
    ),
    summary="Autonomous coding agent powered by Claude Code",
    examples=[
        "Write a TypeScript function to parse JSON",
        "Read and analyze the package.json file",
        "Analyze stack traces and identify root causes",
        "Debug this error in the codebase",
    ],
    llm={"provider": "anthropic", "model": "claude-haiku-4-5"},
    environment={
        "required": [
            {
                "name": "ANTHROPIC_API_KEY",
                "description": "Anthropic API key for Claude API access",
                "linkRef": {"provider": "anthropic", "key": "api_key"},
            },
        ],
        "optional": [
            {
                "name": "GH_TOKEN",
                "description": "GitHub token for gh CLI access to private repos",
                "linkRef": {"provider": "github", "key": "access_token"},
            },
        ],
    },
    use_workspace_skills=True,
)
def execute(prompt: str, ctx) -> OkResult | ErrResult:
    # --- Validate required env ---
    api_key = ctx.env.get("ANTHROPIC_API_KEY")
    if not api_key:
        return err("ANTHROPIC_API_KEY not set. Connect Anthropic in Link.")

    # Helper for phase-level progress (no-op if stream unavailable)
    def _progress(msg: str) -> None:
        if ctx.stream:
            ctx.stream.progress(msg, tool_name="Claude Code")

    # --- Phase 1: Pre-processing (extract repo/task/effort with Haiku) ---
    _progress("Analyzing task")
    prep = None
    try:
        result = ctx.llm.generate_object(
            messages=[
                {
                    "role": "user",
                    "content": f"{_EXTRACTION_PROMPT}{prompt}",
                }
            ],
            schema=_EXTRACTION_SCHEMA,
        )
        prep = result.object
    except Exception:
        # Graceful degradation — use original prompt
        pass

    effective_prompt = prep["task"] if prep else prompt
    effort = prep["effort"] if prep else "medium"
    repo = prep.get("repo") if prep else None

    # --- Phase 2: Model + fallback selection ---
    model, fallback_model = _select_model(effort)

    # --- Phase 3: Build provider options ---
    output_schema = ctx.config.get("outputSchema") if ctx.config else None
    skills = ctx.config.get("skills") if ctx.config else None
    system_append = _build_system_append(skills)

    provider_options = {
        "systemPrompt": {
            "type": "preset",
            "preset": "claude_code",
            "append": system_append,
        },
        "effort": effort,
        "fallbackModel": fallback_model,
        "env": {
            "ANTHROPIC_API_KEY": api_key,
            "GH_TOKEN": ctx.env.get("GH_TOKEN", ""),
        },
    }

    # Only pass repo if no existing workspace (FSM pipeline may have set one up)
    existing_work_dir = ctx.config.get("workDir") if ctx.config else None
    if not existing_work_dir and repo:
        provider_options["repo"] = repo
    elif existing_work_dir:
        provider_options["cwd"] = existing_work_dir

    if output_schema:
        provider_options["outputSchema"] = output_schema

    # --- Phase 4: Call claude-code "LLM" ---
    _progress("Starting Claude Code")
    result = ctx.llm.generate(
        messages=[{"role": "user", "content": effective_prompt}],
        model=model,
        provider_options=provider_options,
    )

    response_text = result.text or ""

    # --- Phase 5: Artifact creation (best-effort) ---
    _progress("Saving artifact")
    artifact_data = json.dumps(result.object) if result.object else response_text
    artifact_ref = _create_artifact(ctx, prompt, artifact_data)
    extras = AgentExtras(artifact_refs=[artifact_ref]) if artifact_ref else None

    # --- Phase 6: Structured output extraction (3-level fallback) ---
    if output_schema:
        # Level 1: Provider returned structured data
        if result.object and isinstance(result.object, dict):
            return ok(result.object, extras)
        # Level 2: Parse JSON from response text (must be dict, not array)
        parsed = _parse_structured_output(response_text)
        if parsed is not None:
            return ok(parsed, extras)
        # Level 3: Wrap as text
        return ok({"response": response_text}, extras)

    return ok({"response": response_text}, extras)
