"""Bitbucket agent — deterministic PR operations via the Bitbucket REST API v2.

Port of packages/bundled-agents/src/bb/agent.ts to Python.
Uses parse_input to extract operation configs from enriched prompts,
then dispatches to handlers that call Bitbucket API via ctx.http.
"""

import base64
import json
import re
import uuid
from dataclasses import dataclass
from urllib.parse import urlparse

from friday_agent_sdk import ErrResult, OkResult, agent, err, ok, parse_operation, run


@dataclass
class PrViewConfig:
    operation: str
    pr_url: str
    fields: list[str] | None = None


@dataclass
class PrDiffConfig:
    operation: str
    pr_url: str
    name_only: bool = False


@dataclass
class PrFilesConfig:
    operation: str
    pr_url: str


@dataclass
class PrReadThreadsConfig:
    operation: str
    pr_url: str


@dataclass
class PrReviewConfig:
    operation: str
    pr_url: str
    body: str


@dataclass
class PrCreateConfig:
    operation: str
    repo_url: str
    source_branch: str
    title: str
    destination_branch: str = "main"
    description: str | None = None
    issue_key: str | None = None
    summary: str | None = None
    files_changed: list[str] | None = None
    close_source_branch: bool = True


@dataclass
class PrInlineReviewConfig:
    operation: str
    pr_url: str
    verdict: str
    summary: str
    findings: list
    commit_id: str | None = None


@dataclass
class PrPostFollowupConfig:
    operation: str
    pr_url: str
    summary: str
    thread_replies: list
    new_findings: list
    commit_id: str | None = None


@dataclass
class CloneConfig:
    operation: str
    pr_url: str


@dataclass
class RepoCloneConfig:
    operation: str
    repo_url: str
    branch: str | None = None


@dataclass
class RepoPushConfig:
    operation: str
    path: str
    branch: str
    repo_url: str


# Map operation name to its typed config dataclass
_OPERATION_SCHEMAS: dict[str, type] = {
    "pr-view": PrViewConfig,
    "pr-diff": PrDiffConfig,
    "pr-files": PrFilesConfig,
    "pr-read-threads": PrReadThreadsConfig,
    "pr-review": PrReviewConfig,
    "pr-inline-review": PrInlineReviewConfig,
    "pr-post-followup": PrPostFollowupConfig,
    "pr-create": PrCreateConfig,
    "clone": CloneConfig,
    "repo-clone": RepoCloneConfig,
    "repo-push": RepoPushConfig,
}


def _parse_pr_url(pr_url: str) -> dict:
    """Parse a Bitbucket PR URL into workspace, repo_slug, pr_id.

    Accepts: https://bitbucket.org/workspace/repo_slug/pull-requests/123
    """
    parsed = urlparse(pr_url)
    if parsed.hostname != "bitbucket.org":
        raise ValueError(f"Expected bitbucket.org URL, got: {parsed.hostname}")

    segments = [s for s in parsed.path.split("/") if s]
    if len(segments) < 4 or segments[2] != "pull-requests":
        raise ValueError(f"Invalid PR URL path: {parsed.path}. Expected: /workspace/repo_slug/pull-requests/123")

    return {
        "workspace": segments[0],
        "repo_slug": segments[1],
        "pr_id": int(segments[3]),
    }


def _parse_repo_url(repo_url: str) -> dict:
    """Parse a Bitbucket repo URL into workspace, repo_slug.

    Accepts: https://bitbucket.org/workspace/repo_slug[/src/main/...]
    """
    parsed = urlparse(repo_url)
    if parsed.hostname != "bitbucket.org":
        raise ValueError(f"Expected bitbucket.org URL, got: {parsed.hostname}")

    segments = [s for s in parsed.path.split("/") if s]
    if len(segments) < 2:
        raise ValueError(f"Invalid repo URL: {parsed.path}")

    return {
        "workspace": segments[0],
        "repo_slug": segments[1],
    }


def _bb_auth_header(ctx) -> dict[str, str]:
    """Build Basic Auth header from ctx.env credentials."""
    email = ctx.env.get("BITBUCKET_EMAIL", "")
    token = ctx.env.get("BITBUCKET_TOKEN", "")
    if not email or not token:
        return {}
    credentials = f"{email}:{token}"
    b64 = base64.b64encode(credentials.encode()).decode()
    return {"Authorization": f"Basic {b64}"}


def _bb_fetch(url: str, ctx, *, accept: str = "application/json"):
    """Fetch a Bitbucket API URL with auth headers."""
    headers = {
        "Accept": accept,
        "User-Agent": "friday-bb-agent",
        **_bb_auth_header(ctx),
    }
    return ctx.http.fetch(url, headers=headers)


def _paginate_all(first_url: str, ctx) -> list:
    """Follow Bitbucket pagination, collecting all values."""
    all_values: list = []
    url = first_url
    max_pages = 100
    pages = 0
    while url and pages < max_pages:
        response = _bb_fetch(url, ctx)
        if response.status >= 400:
            break
        data = json.loads(response.body)
        all_values.extend(data.get("values", []))
        url = data.get("next")
        pages += 1
    return all_values


def _pr_view(config: PrViewConfig, ctx) -> OkResult | ErrResult:
    """Fetch PR metadata via Bitbucket REST API v2."""
    parts = _parse_pr_url(config.pr_url)
    workspace = parts["workspace"]
    repo_slug = parts["repo_slug"]
    pr_id = parts["pr_id"]

    response = _bb_fetch(
        f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}",
        ctx,
    )

    if response.status >= 400:
        return err(f"Bitbucket API error {response.status}: {response.body[:500]}")

    data = json.loads(response.body)
    return ok(
        {
            "operation": "pr-view",
            "success": True,
            "data": {
                "title": data.get("title"),
                "description": data.get("description"),
                "author": data.get("author", {}).get("display_name"),
                "author_uuid": data.get("author", {}).get("uuid"),
                "state": data.get("state"),
                "source_branch": data.get("source", {}).get("branch", {}).get("name"),
                "destination_branch": (data.get("destination", {}).get("branch", {}).get("name")),
                "head_sha": data.get("source", {}).get("commit", {}).get("hash"),
                "created_on": data.get("created_on"),
                "updated_on": data.get("updated_on"),
            },
        }
    )


def _pr_diff(config: PrDiffConfig, ctx) -> OkResult | ErrResult:
    """Fetch PR diff or file list via Bitbucket REST API v2."""
    parts = _parse_pr_url(config.pr_url)
    workspace = parts["workspace"]
    repo_slug = parts["repo_slug"]
    pr_id = parts["pr_id"]

    url = f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/diff"
    response = _bb_fetch(url, ctx, accept="text/plain")

    if response.status >= 400:
        return err(f"Bitbucket API error {response.status}: {response.body[:500]}")

    if config.name_only:
        files = re.findall(r"^diff --git a/.+ b/(.+)$", response.body, re.MULTILINE)
        return ok(
            {
                "operation": "pr-diff",
                "success": True,
                "data": {"files": files, "count": len(files)},
            }
        )

    return ok(
        {
            "operation": "pr-diff",
            "success": True,
            "data": {"diff": response.body},
        }
    )


def _pr_files(config: PrFilesConfig, ctx) -> OkResult | ErrResult:
    """Fetch list of changed files in a PR via Bitbucket diffstat API."""
    parts = _parse_pr_url(config.pr_url)
    workspace = parts["workspace"]
    repo_slug = parts["repo_slug"]
    pr_id = parts["pr_id"]

    url = f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/diffstat"
    entries = _paginate_all(url, ctx)

    files = [entry.get("new", {}).get("path") or entry.get("old", {}).get("path", "") for entry in entries]
    return ok(
        {
            "operation": "pr-files",
            "success": True,
            "data": {"files": files, "count": len(files)},
        }
    )


def _pr_read_threads(config: PrReadThreadsConfig, ctx) -> OkResult | ErrResult:
    """Fetch PR comment threads via Bitbucket REST API v2.

    Gets all comments, groups into threads (root + replies).
    """
    parts = _parse_pr_url(config.pr_url)
    workspace = parts["workspace"]
    repo_slug = parts["repo_slug"]
    pr_id = parts["pr_id"]

    url = f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/comments"
    comments = _paginate_all(url, ctx)

    roots: dict[int, dict] = {}
    orphan_replies: list[dict] = []

    for c in comments:
        if not c.get("parent"):
            inline = c.get("inline")
            roots[c["id"]] = {
                "comment_id": c["id"],
                "path": inline.get("path") if inline else None,
                "line": (inline.get("to") or inline.get("from")) if inline else None,
                "body": c.get("content", {}).get("raw", ""),
                "user": c.get("user", {}).get("uuid", ""),
                "replies": [],
            }
        else:
            orphan_replies.append(c)

    for r in orphan_replies:
        parent_id = r.get("parent", {}).get("id")
        if parent_id in roots:
            roots[parent_id]["replies"].append(
                {
                    "user": r.get("user", {}).get("uuid", ""),
                    "body": r.get("content", {}).get("raw", ""),
                    "created_at": r.get("created_on", ""),
                }
            )

    threads = list(roots.values())
    return ok(
        {
            "operation": "pr-read-threads",
            "success": True,
            "data": {
                "threads": threads,
                "total_threads": len(threads),
                "threads_with_replies": sum(1 for t in threads if len(t["replies"]) > 0),
            },
        }
    )


def _pr_review(config: PrReviewConfig, ctx) -> OkResult | ErrResult:
    """Post a general comment on a PR via Bitbucket REST API v2."""
    parts = _parse_pr_url(config.pr_url)
    workspace = parts["workspace"]
    repo_slug = parts["repo_slug"]
    pr_id = parts["pr_id"]

    url = f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/comments"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "friday-bb-agent",
        **_bb_auth_header(ctx),
    }
    body = json.dumps({"content": {"raw": config.body}})

    response = ctx.http.fetch(url, method="POST", headers=headers, body=body)

    if response.status >= 400:
        return err(f"Bitbucket API error {response.status}: {response.body[:500]}")

    data = json.loads(response.body)
    return ok(
        {
            "operation": "pr-review",
            "success": True,
            "data": {
                "pr_number": pr_id,
                "repo": f"{workspace}/{repo_slug}",
                "comment_id": data.get("id"),
            },
        }
    )


def _build_comment_body(finding: dict) -> str:
    """Build the markdown body for an inline PR comment from a finding.

    Matches the TS buildCommentBody() format exactly.
    """
    parts = [
        f"**{finding['severity']}** — {finding['title']}",
        "",
        f"**Category:** {finding['category']}",
        "",
        finding["description"],
    ]

    if finding.get("suggestion"):
        parts.extend(["", "```suggestion", finding["suggestion"], "```"])

    return "\n".join(parts)


def _build_failed_findings_summary(failed: list[dict], findings: list[dict]) -> list[str]:
    """Build summary sections for findings that failed to post inline.

    Matches the TS buildFailedFindingsSummary() format exactly.
    """
    parts: list[str] = []
    for f in failed:
        finding = next(
            (x for x in findings if x["file"] == f["path"] and x["line"] == f["line"]),
            None,
        )
        if finding:
            suggestion_block = f"\n**Suggestion:**\n```\n{finding['suggestion']}\n```" if finding.get("suggestion") else ""
            parts.extend(
                [
                    "",
                    "<details>",
                    f"<summary><b>{finding['severity']}</b> · "
                    f"<code>{finding['file']}:{finding['line']}</code>"
                    f" — {finding['title']}</summary>",
                    "",
                    f"**Category:** {finding['category']}",
                    "",
                    finding["description"],
                    suggestion_block,
                    "",
                    "</details>",
                ]
            )
    return parts


def _post_inline_comments(
    findings: list[dict], workspace: str, repo_slug: str, pr_id: int, ctx
) -> tuple[list[dict], list[dict]]:
    """Post inline comments for each finding. Returns (posted, failed) lists."""
    url = f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/comments"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "friday-bb-agent",
        **_bb_auth_header(ctx),
    }

    posted: list[dict] = []
    failed: list[dict] = []

    for finding in findings:
        body = _build_comment_body(finding)
        payload = json.dumps(
            {
                "content": {"raw": body},
                "inline": {"path": finding["file"], "to": finding["line"]},
            }
        )
        response = ctx.http.fetch(url, method="POST", headers=headers, body=payload)
        if response.status >= 400:
            failed.append(
                {
                    "path": finding["file"],
                    "line": finding["line"],
                    "error": f"HTTP {response.status}",
                }
            )
        else:
            posted.append({"path": finding["file"], "line": finding["line"]})

    return posted, failed


def _post_general_comment(body: str, workspace: str, repo_slug: str, pr_id: int, ctx) -> None:
    """Post a general (non-inline) comment on a PR."""
    url = f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/comments"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "friday-bb-agent",
        **_bb_auth_header(ctx),
    }
    payload = json.dumps({"content": {"raw": body}})
    ctx.http.fetch(url, method="POST", headers=headers, body=payload)


def _pr_inline_review(config: PrInlineReviewConfig, ctx) -> OkResult | ErrResult:
    """Post inline code review findings on a PR."""
    parts = _parse_pr_url(config.pr_url)
    workspace = parts["workspace"]
    repo_slug = parts["repo_slug"]
    pr_id = parts["pr_id"]

    posted, failed = _post_inline_comments(config.findings, workspace, repo_slug, pr_id, ctx)

    total = len(config.findings)
    summary_parts = [
        "## Code Review",
        "",
        f"**Verdict:** {config.verdict}",
        "",
        "### Summary",
        "",
        config.summary,
        "",
        "---",
        "",
        f"> {total} findings: {len(posted)} inline" + (f", {len(failed)} in summary (outside diff range)" if failed else ""),
        *_build_failed_findings_summary(failed, config.findings),
        "",
        "---",
        "",
        "*Automated review by Friday*",
    ]

    _post_general_comment("\n".join(summary_parts), workspace, repo_slug, pr_id, ctx)

    return ok(
        {
            "operation": "pr-inline-review",
            "success": True,
            "data": {
                "pr_number": pr_id,
                "repo": f"{workspace}/{repo_slug}",
                "posted_comments": len(posted),
                "failed_comments": len(failed),
            },
        }
    )


def _pr_post_followup(config: PrPostFollowupConfig, ctx) -> OkResult | ErrResult:
    """Post follow-up replies to existing threads and new inline findings."""
    parts = _parse_pr_url(config.pr_url)
    workspace = parts["workspace"]
    repo_slug = parts["repo_slug"]
    pr_id = parts["pr_id"]

    url = f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/comments"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "friday-bb-agent",
        **_bb_auth_header(ctx),
    }

    # Post thread replies
    replies_posted = 0
    for reply in config.thread_replies:
        payload = json.dumps(
            {
                "content": {"raw": reply["body"]},
                "parent": {"id": reply["comment_id"]},
            }
        )
        response = ctx.http.fetch(url, method="POST", headers=headers, body=payload)
        if response.status < 400:
            replies_posted += 1
        # Silently skip failed replies (thread may be outdated/deleted)

    # Post new inline findings
    posted, failed = _post_inline_comments(config.new_findings, workspace, repo_slug, pr_id, ctx)

    # Post summary comment
    summary_parts = [
        "## Follow-up Review",
        "",
        config.summary,
        "",
        "---",
        "",
        f"> {replies_posted} thread replies, {len(posted)} new inline comments"
        + (f", {len(failed)} in summary" if failed else ""),
        *_build_failed_findings_summary(failed, config.new_findings),
        "",
        "---",
        "",
        "*Automated follow-up by Friday*",
    ]

    _post_general_comment("\n".join(summary_parts), workspace, repo_slug, pr_id, ctx)

    return ok(
        {
            "operation": "pr-post-followup",
            "success": True,
            "data": {
                "pr_number": pr_id,
                "repo": f"{workspace}/{repo_slug}",
                "thread_replies_posted": replies_posted,
                "new_comments_posted": len(posted),
                "failed_comments": len(failed),
            },
        }
    )


def _pr_create(config: PrCreateConfig, ctx) -> OkResult | ErrResult:
    """Create a new PR via Bitbucket REST API v2."""
    parts = _parse_repo_url(config.repo_url)
    workspace = parts["workspace"]
    repo_slug = parts["repo_slug"]

    if config.description:
        desc = config.description
    else:
        desc_parts: list[str] = []
        if config.issue_key:
            desc_parts.append(f"Fixes {config.issue_key}")
        if config.summary:
            desc_parts.append(f"\n\n{config.summary}")
        if config.files_changed:
            desc_parts.append("\n\n### Changes")
            for f in config.files_changed:
                desc_parts.append(f"\n- {f}")
        desc_parts.append("\n\n---\n\n*Automated by Friday*")
        desc = "".join(desc_parts)

    url = f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/pullrequests"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "friday-bb-agent",
        **_bb_auth_header(ctx),
    }
    body = json.dumps(
        {
            "title": config.title,
            "description": desc,
            "source": {"branch": {"name": config.source_branch}},
            "destination": {"branch": {"name": config.destination_branch}},
            "close_source_branch": config.close_source_branch,
        }
    )

    response = ctx.http.fetch(url, method="POST", headers=headers, body=body)

    if response.status >= 400:
        return err(f"Bitbucket API error {response.status}: {response.body[:500]}")

    data = json.loads(response.body)
    return ok(
        {
            "operation": "pr-create",
            "success": True,
            "data": {
                "pr_number": data.get("id"),
                "pr_url": data.get("links", {}).get("html", {}).get("href"),
                "repo": f"{workspace}/{repo_slug}",
                "source_branch": config.source_branch,
                "destination_branch": config.destination_branch,
                "title": config.title,
            },
        }
    )


def _git_credential_env(ctx) -> dict[str, str]:
    """Build env vars for GIT_ASKPASS-based credential injection.

    Creates an inline askpass script that echoes the username or password
    depending on the prompt. Credentials never appear in URLs.
    """
    token = ctx.env.get("BITBUCKET_TOKEN", "")
    askpass_script = (
        "#!/bin/sh\n"
        'case "$1" in\n'
        "*Username*) printf '%s\\n' \"$BB_ASKPASS_USER\";;\n"
        "*Password*) printf '%s\\n' \"$BB_ASKPASS_PASS\";;\n"
        "esac\n"
    )
    askpass_path = f"/tmp/bb-askpass-{uuid.uuid4()}.sh"
    return {
        "_askpass_path": askpass_path,
        "_askpass_script": askpass_script,
        "GIT_TERMINAL_PROMPT": "0",
        "BB_ASKPASS_USER": "x-bitbucket-api-token-auth",
        "BB_ASKPASS_PASS": token,
    }


def _bash(ctx, command: str, env: dict[str, str] | None = None) -> dict:
    """Call the bash tool, returning the parsed result dict.

    Raises RuntimeError if exit_code != 0.
    """
    args: dict = {"command": command}
    if env:
        args["env"] = env
    result = ctx.tools.call("bash", args)
    if result.get("exit_code", 0) != 0:
        stderr = result.get("stderr", "")
        raise RuntimeError(f"Command failed (exit {result['exit_code']}): {stderr}")
    return result


def _clone(config: CloneConfig, ctx) -> OkResult | ErrResult:
    """Clone a repo for a specific PR.

    Fetch metadata, clone, checkout source branch, get changed files.
    """
    parts = _parse_pr_url(config.pr_url)
    workspace = parts["workspace"]
    repo_slug = parts["repo_slug"]
    pr_id = parts["pr_id"]

    # Fetch PR metadata via API
    response = _bb_fetch(
        f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}",
        ctx,
    )
    if response.status >= 400:
        return err(f"Failed to fetch PR #{pr_id}: API error {response.status}")

    pr = json.loads(response.body)
    source_branch = pr.get("source", {}).get("branch", {}).get("name")
    dest_branch = pr.get("destination", {}).get("branch", {}).get("name")
    head_sha = pr.get("source", {}).get("commit", {}).get("hash")

    if not source_branch:
        return err("PR source branch not found in metadata")

    # Clone repo and checkout source branch
    clone_dir = f"/tmp/bb-clone-{uuid.uuid4()}"
    clone_url = f"https://bitbucket.org/{workspace}/{repo_slug}.git"
    cred_env = _git_credential_env(ctx)
    askpass_path = cred_env.pop("_askpass_path")
    askpass_script = cred_env.pop("_askpass_script")

    try:
        _bash(
            ctx,
            f"cat > {askpass_path} << 'ASKPASS_EOF'\n{askpass_script}ASKPASS_EOF\nchmod 700 {askpass_path}",
        )

        git_env = {**cred_env, "GIT_ASKPASS": askpass_path}
        _bash(
            ctx,
            f"git -c credential.helper= clone {clone_url} {clone_dir}",
            env=git_env,
        )

        _bash(
            ctx,
            f"cd {clone_dir} && git checkout {source_branch}",
            env=git_env,
        )
        branch_result = _bash(
            ctx,
            f"cd {clone_dir} && git branch --show-current",
            env=git_env,
        )
        branch = branch_result.get("stdout", "").strip() or source_branch

        _bash(ctx, f"rm -f {askpass_path}")
    except RuntimeError as e:
        try:
            _bash(ctx, f"rm -rf {clone_dir} {askpass_path}")
        except RuntimeError:
            pass
        return err(f"clone failed: {e}")

    # Fetch changed files via diffstat API
    diffstat_url = f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/diffstat"
    entries = _paginate_all(diffstat_url, ctx)
    changed_files = [entry.get("new", {}).get("path") or entry.get("old", {}).get("path", "") for entry in entries]

    return ok(
        {
            "operation": "clone",
            "success": True,
            "data": {
                "path": clone_dir,
                "repo": f"{workspace}/{repo_slug}",
                "branch": branch,
                "base_branch": dest_branch,
                "pr_number": pr_id,
                "pr_url": config.pr_url,
                "head_sha": head_sha,
                "pr_metadata": {
                    "title": pr.get("title"),
                    "description": pr.get("description"),
                    "author": pr.get("author", {}).get("display_name"),
                    "state": pr.get("state"),
                },
                "changed_files": changed_files,
            },
        }
    )


def _repo_clone(config: RepoCloneConfig, ctx) -> OkResult | ErrResult:
    """Clone a Bitbucket repo via git, optionally checking out a branch."""
    parts = _parse_repo_url(config.repo_url)
    workspace = parts["workspace"]
    repo_slug = parts["repo_slug"]

    clone_dir = f"/tmp/bb-clone-{uuid.uuid4()}"
    clone_url = f"https://bitbucket.org/{workspace}/{repo_slug}.git"
    cred_env = _git_credential_env(ctx)
    askpass_path = cred_env.pop("_askpass_path")
    askpass_script = cred_env.pop("_askpass_script")

    try:
        # ASKPASS_EOF prevents shell expansion of heredoc content
        _bash(
            ctx,
            f"cat > {askpass_path} << 'ASKPASS_EOF'\n{askpass_script}ASKPASS_EOF\nchmod 700 {askpass_path}",
        )

        git_env = {**cred_env, "GIT_ASKPASS": askpass_path}
        _bash(
            ctx,
            f"git -c credential.helper= clone {clone_url} {clone_dir}",
            env=git_env,
        )

        # Checkout branch if specified
        if config.branch:
            _bash(ctx, f"cd {clone_dir} && git checkout {config.branch}", env=git_env)

        # Get current branch name
        result = _bash(ctx, f"cd {clone_dir} && git branch --show-current", env=git_env)
        branch = result.get("stdout", "").strip() or "main"

        # Cleanup askpass script
        _bash(ctx, f"rm -f {askpass_path}")

        return ok(
            {
                "operation": "repo-clone",
                "success": True,
                "data": {
                    "path": clone_dir,
                    "repo": f"{workspace}/{repo_slug}",
                    "branch": branch,
                },
            }
        )
    except RuntimeError as e:
        # Cleanup on failure
        try:
            _bash(ctx, f"rm -rf {clone_dir} {askpass_path}")
        except RuntimeError:
            pass
        return err(f"repo-clone failed: {e}")


def _repo_push(config: RepoPushConfig, ctx) -> OkResult | ErrResult:
    """Push a local branch to the remote Bitbucket repo."""
    parts = _parse_repo_url(config.repo_url)
    workspace = parts["workspace"]
    repo_slug = parts["repo_slug"]

    cred_env = _git_credential_env(ctx)
    askpass_path = cred_env.pop("_askpass_path")
    askpass_script = cred_env.pop("_askpass_script")

    try:
        # ASKPASS_EOF prevents shell expansion of heredoc content
        _bash(
            ctx,
            f"cat > {askpass_path} << 'ASKPASS_EOF'\n{askpass_script}ASKPASS_EOF\nchmod 700 {askpass_path}",
        )

        git_env = {**cred_env, "GIT_ASKPASS": askpass_path}
        _bash(
            ctx,
            f"cd {config.path} && git -c credential.helper= push -u origin {config.branch}",
            env=git_env,
        )

        # Cleanup askpass script
        _bash(ctx, f"rm -f {askpass_path}")

        return ok(
            {
                "operation": "repo-push",
                "success": True,
                "data": {
                    "repo": f"{workspace}/{repo_slug}",
                    "branch": config.branch,
                },
            }
        )
    except RuntimeError as e:
        try:
            _bash(ctx, f"rm -f {askpass_path}")
        except RuntimeError:
            pass
        return err(f"repo-push failed: {e}")


@agent(id="bb", version="1.0.0", description="Bitbucket PR operations agent")
def execute(prompt: str, ctx):
    """Parse operation from prompt and dispatch to handler.

    Single-pass parsing: filters to JSON objects containing "operation",
    uses the discriminator to select the right schema, validates in one step.
    """
    try:
        config = parse_operation(prompt, _OPERATION_SCHEMAS)
    except ValueError as e:
        return err(str(e))

    operation = config.operation

    match operation:
        case "pr-view":
            return _pr_view(config, ctx)
        case "pr-diff":
            return _pr_diff(config, ctx)
        case "pr-files":
            return _pr_files(config, ctx)
        case "pr-read-threads":
            return _pr_read_threads(config, ctx)
        case "pr-review":
            return _pr_review(config, ctx)
        case "pr-inline-review":
            return _pr_inline_review(config, ctx)
        case "pr-post-followup":
            return _pr_post_followup(config, ctx)
        case "pr-create":
            return _pr_create(config, ctx)
        case "clone":
            return _clone(config, ctx)
        case "repo-clone":
            return _repo_clone(config, ctx)
        case "repo-push":
            return _repo_push(config, ctx)


if __name__ == "__main__":
    run()
