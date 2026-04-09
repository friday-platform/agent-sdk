"""GitHub agent — deterministic PR operations via the GitHub API.

Port of packages/bundled-agents/src/gh/agent.ts to Python.
Uses parse_input to extract operation configs from enriched prompts,
then dispatches to handlers that call GitHub API via ctx.http.
"""

import json
import uuid
from dataclasses import dataclass
from urllib.parse import urlparse

from friday_agent_sdk import agent, err, ok, parse_input
from friday_agent_sdk._bridge import Agent  # noqa: F401 — componentize-py needs this
from friday_agent_sdk._result import ErrResult, OkResult


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
class CloneConfig:
    operation: str
    pr_url: str


@dataclass
class PrReviewConfig:
    operation: str
    pr_url: str
    body: str


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
    thread_replies: list | None = None
    new_findings: list | None = None
    commit_id: str | None = None


# Map operation name to its typed config dataclass
_OPERATION_SCHEMAS: dict[str, type] = {
    "clone": CloneConfig,
    "pr-view": PrViewConfig,
    "pr-diff": PrDiffConfig,
    "pr-files": PrFilesConfig,
    "pr-read-threads": PrReadThreadsConfig,
    "pr-review": PrReviewConfig,
    "pr-inline-review": PrInlineReviewConfig,
    "pr-post-followup": PrPostFollowupConfig,
}


def _parse_pr_url(pr_url: str) -> dict:
    """Parse a GitHub PR URL into owner, repo, pr_number.

    Accepts: https://github.com/owner/repo/pull/123
    """
    parsed = urlparse(pr_url)
    if parsed.hostname != "github.com":
        raise ValueError(f"Expected github.com URL, got: {parsed.hostname}")

    segments = [s for s in parsed.path.split("/") if s]
    if len(segments) < 4 or segments[2] != "pull":
        raise ValueError(
            f"Invalid PR URL path: {parsed.path}. Expected: /owner/repo/pull/123"
        )

    return {
        "owner": segments[0],
        "repo": segments[1],
        "pr_number": int(segments[3]),
    }


def _clone(config: CloneConfig, ctx) -> OkResult | ErrResult:
    """Clone a repo and check out a PR's head branch.

    Uses ctx.http.fetch for PR metadata and ctx.tools.call("bash", ...)
    for git commands. GitHub auth via GH_TOKEN env var passed through
    git credential helper environment.
    """
    parts = _parse_pr_url(config.pr_url)
    owner, repo, pr_number = parts["owner"], parts["repo"], parts["pr_number"]
    nwo = f"{owner}/{repo}"
    gh_token = ctx.env.get("GH_TOKEN", "")

    # Fetch PR metadata (auth required for private repos)
    meta_headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "friday-gh-agent",
    }
    if gh_token:
        meta_headers["Authorization"] = f"Bearer {gh_token}"
    meta_resp = ctx.http.fetch(
        f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}",
        headers=meta_headers,
    )
    if meta_resp.status >= 400:
        return err(f"GitHub API error {meta_resp.status}: {meta_resp.body[:500]}")
    pr_data = json.loads(meta_resp.body)

    head_ref = pr_data["head"]["ref"]
    head_sha = pr_data["head"]["sha"]
    base_ref = pr_data["base"]["ref"]
    clone_url = f"https://github.com/{nwo}.git"
    clone_dir = f"/tmp/gh-clone-{uuid.uuid4()}"

    # Clone using GH_TOKEN via GIT_ASKPASS to avoid token in URL (security)
    # credential.helper env var provides token without touching disk
    clone_result = ctx.tools.call(
        "bash",
        {
            "command": f"git clone --quiet {clone_url} {clone_dir}",
            "env": {
                "GIT_ASKPASS": "echo",
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_USERNAME": "x-access-token",
                "GIT_PASSWORD": gh_token,
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "credential.helper",
                "GIT_CONFIG_VALUE_0": (
                    "!f() { echo username=x-access-token; "
                    f"echo password={gh_token}; "
                    "};f"
                ),
            },
        },
    )

    if clone_result.get("exit_code", 1) != 0:
        # Attempt cleanup
        ctx.tools.call(
            "bash",
            {
                "command": f"rm -rf {clone_dir}",
            },
        )
        stderr = clone_result.get("stderr", "")
        return err(f"git clone failed: {stderr}")

    # Checkout the PR head branch
    checkout_result = ctx.tools.call(
        "bash",
        {
            "command": f"cd {clone_dir} && git checkout --quiet {head_ref}",
        },
    )

    if checkout_result.get("exit_code", 1) != 0:
        ctx.tools.call("bash", {"command": f"rm -rf {clone_dir}"})
        stderr = checkout_result.get("stderr", "")
        return err(f"git checkout failed: {stderr}")

    # Fetch changed files via API — /files is paginated, may need follow-up calls
    files_resp = ctx.http.fetch(
        f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files",
        headers={
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "friday-gh-agent",
        },
    )

    changed_files: list[str] = []
    if files_resp.status < 400:
        files_data = json.loads(files_resp.body)
        changed_files = [f["filename"] for f in files_data]

    return ok(
        {
            "operation": "clone",
            "success": True,
            "data": {
                "path": clone_dir,
                "repo": nwo,
                "branch": head_ref,
                "base_branch": base_ref,
                "pr_number": pr_number,
                "pr_url": config.pr_url,
                "head_sha": head_sha,
                "pr_metadata": {
                    "title": pr_data.get("title", ""),
                    "state": pr_data.get("state", ""),
                    "author": pr_data.get("user", {}).get("login", ""),
                },
                "changed_files": changed_files,
            },
        }
    )


def _pr_view(config: PrViewConfig, ctx) -> OkResult | ErrResult:
    """Fetch PR metadata via GitHub REST API."""
    parts = _parse_pr_url(config.pr_url)
    owner, repo, pr_number = parts["owner"], parts["repo"], parts["pr_number"]

    response = ctx.http.fetch(
        f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}",
        headers={
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "friday-gh-agent",
        },
    )

    if response.status >= 400:
        return err(f"GitHub API error {response.status}: {response.body[:500]}")

    data = json.loads(response.body)
    return ok(
        {
            "operation": "pr-view",
            "success": True,
            "data": {
                "title": data.get("title"),
                "state": data.get("state"),
                "user": data.get("user", {}).get("login"),
                "base_ref": data.get("base", {}).get("ref"),
                "head_ref": data.get("head", {}).get("ref"),
                "additions": data.get("additions"),
                "deletions": data.get("deletions"),
                "changed_files": data.get("changed_files"),
            },
        }
    )


def _pr_diff(config: PrDiffConfig, ctx) -> OkResult | ErrResult:
    """Fetch PR diff or file list via GitHub REST API."""
    parts = _parse_pr_url(config.pr_url)
    owner, repo, pr_number = parts["owner"], parts["repo"], parts["pr_number"]

    if config.name_only:
        # Use /files endpoint and extract filenames
        response = ctx.http.fetch(
            f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files",
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "friday-gh-agent",
            },
        )

        if response.status >= 400:
            return err(f"GitHub API error {response.status}: {response.body[:500]}")

        files_data = json.loads(response.body)
        files = [f["filename"] for f in files_data]
        return ok(
            {
                "operation": "pr-diff",
                "success": True,
                "data": {"files": files, "count": len(files)},
            }
        )

    # Full diff via Accept: application/vnd.github.diff
    response = ctx.http.fetch(
        f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}",
        headers={
            "Accept": "application/vnd.github.diff",
            "User-Agent": "friday-gh-agent",
        },
    )

    if response.status >= 400:
        return err(f"GitHub API error {response.status}: {response.body[:500]}")

    return ok(
        {
            "operation": "pr-diff",
            "success": True,
            "data": {"diff": response.body},
        }
    )


def _pr_files(config: PrFilesConfig, ctx) -> OkResult | ErrResult:
    """Fetch list of changed files in a PR via GitHub REST API."""
    parts = _parse_pr_url(config.pr_url)
    owner, repo, pr_number = parts["owner"], parts["repo"], parts["pr_number"]

    response = ctx.http.fetch(
        f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files",
        headers={
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "friday-gh-agent",
        },
    )

    if response.status >= 400:
        return err(f"GitHub API error {response.status}: {response.body[:500]}")

    files_data = json.loads(response.body)
    files = [{"filename": f["filename"], "status": f["status"]} for f in files_data]
    return ok(
        {
            "operation": "pr-files",
            "success": True,
            "data": {"files": files, "count": len(files)},
        }
    )


def _pr_read_threads(config: PrReadThreadsConfig, ctx) -> OkResult | ErrResult:
    """Fetch PR review comment threads via GitHub REST API.

    Gets all review comments, groups them into threads (root + replies).
    Ported from: packages/bundled-agents/src/gh/agent.ts
    """
    parts = _parse_pr_url(config.pr_url)
    owner, repo, pr_number = parts["owner"], parts["repo"], parts["pr_number"]

    response = ctx.http.fetch(
        f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/comments",
        headers={
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "friday-gh-agent",
        },
    )

    if response.status >= 400:
        return err(f"GitHub API error {response.status}: {response.body[:500]}")

    comments = json.loads(response.body)

    # Group into threads: root comments (no in_reply_to_id) with their replies
    roots: dict[int, dict] = {}
    orphan_replies: list[dict] = []

    for c in comments:
        if not c.get("in_reply_to_id"):
            roots[c["id"]] = {
                "comment_id": c["id"],
                "path": c.get("path", ""),
                "line": c.get("line") or c.get("original_line"),
                "body": c.get("body", ""),
                "user": c.get("user", {}).get("login", ""),
                "replies": [],
            }
        else:
            orphan_replies.append(
                {
                    "in_reply_to_id": c["in_reply_to_id"],
                    "user": c.get("user", {}).get("login", ""),
                    "body": c.get("body", ""),
                    "created_at": c.get("created_at", ""),
                }
            )

    for r in orphan_replies:
        root = roots.get(r["in_reply_to_id"])
        if root:
            root["replies"].append(
                {
                    "user": r["user"],
                    "body": r["body"],
                    "created_at": r["created_at"],
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
                "threads_with_replies": sum(
                    1 for t in threads if len(t["replies"]) > 0
                ),
            },
        }
    )


def _gh_headers(ctx) -> dict[str, str]:
    """Build GitHub API request headers with Bearer auth.

    GitHub uses Bearer tokens (not Basic) for personal access tokens.
    See: https://docs.github.com/en/rest/authentication/authenticating-to-the-rest-api
    """
    gh_token = ctx.env.get("GH_TOKEN", "")
    return {
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
        "User-Agent": "friday-gh-agent",
        "Authorization": f"Bearer {gh_token}",
    }


def _build_comment_body(finding: dict) -> str:
    """Build markdown body for an inline PR comment from a finding.

    Keep in sync with: packages/bundled-agents/src/vcs/schemas.ts
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


def _build_failed_findings_summary(
    failed: list[dict],
    findings: list[dict],
) -> list[str]:
    """Build summary sections for findings that failed to post inline.

    Keep in sync with: packages/bundled-agents/src/vcs/schemas.ts
    """
    parts: list[str] = []
    for f in failed:
        finding = next(
            (x for x in findings if x["file"] == f["path"] and x["line"] == f["line"]),
            None,
        )
        if finding:
            suggestion_block = (
                f"\n**Suggestion:**\n```\n{finding['suggestion']}\n```"
                if finding.get("suggestion")
                else ""
            )
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
    findings: list[dict],
    owner: str,
    repo: str,
    pr_number: int,
    commit_id: str,
    ctx,
) -> tuple[list[dict], list[dict]]:
    """Post findings as inline PR review comments. Returns (posted, failed).

    Individual posts may fail if line is outside diff range — caller handles
    failed items by including them in the general comment summary.
    """
    posted: list[dict] = []
    failed: list[dict] = []
    nwo = f"{owner}/{repo}"

    for finding in findings:
        body = _build_comment_body(finding)
        payload: dict = {
            "body": body,
            "path": finding["file"],
            "commit_id": commit_id,
            "line": finding["line"],
            "side": "RIGHT",
        }

        if finding.get("start_line") and finding["start_line"] != finding["line"]:
            payload["start_line"] = finding["start_line"]
            payload["start_side"] = "RIGHT"

        response = ctx.http.fetch(
            f"https://api.github.com/repos/{nwo}/pulls/{pr_number}/comments",
            method="POST",
            headers=_gh_headers(ctx),
            body=json.dumps(payload),
        )

        if response.status < 400:
            posted.append({"path": finding["file"], "line": finding["line"]})
        else:
            failed.append(
                {
                    "path": finding["file"],
                    "line": finding["line"],
                    "error": response.body[:200],
                }
            )

    return posted, failed


def _post_review_summary(
    summary_body: str,
    owner: str,
    repo: str,
    pr_number: int,
    ctx,
) -> None:
    """Post a review summary as an issue comment."""
    nwo = f"{owner}/{repo}"
    ctx.http.fetch(
        f"https://api.github.com/repos/{nwo}/issues/{pr_number}/comments",
        method="POST",
        headers=_gh_headers(ctx),
        body=json.dumps({"body": summary_body}),
    )


def _pr_review(config: PrReviewConfig, ctx) -> OkResult | ErrResult:
    """Post a general comment on a PR via GitHub REST API."""
    parts = _parse_pr_url(config.pr_url)
    owner, repo, pr_number = parts["owner"], parts["repo"], parts["pr_number"]
    nwo = f"{owner}/{repo}"

    response = ctx.http.fetch(
        f"https://api.github.com/repos/{nwo}/issues/{pr_number}/comments",
        method="POST",
        headers=_gh_headers(ctx),
        body=json.dumps({"body": config.body}),
    )

    if response.status >= 400:
        return err(f"GitHub API error {response.status}: {response.body[:500]}")

    data = json.loads(response.body)
    return ok(
        {
            "operation": "pr-review",
            "success": True,
            "data": {
                "pr_number": pr_number,
                "repo": nwo,
                "comment_id": data.get("id"),
            },
        }
    )


def _pr_inline_review(config: PrInlineReviewConfig, ctx) -> OkResult | ErrResult:
    """Post inline review comments + summary on a PR via GitHub REST API."""
    parts = _parse_pr_url(config.pr_url)
    owner, repo, pr_number = parts["owner"], parts["repo"], parts["pr_number"]
    nwo = f"{owner}/{repo}"

    # Resolve commit_id: use provided or fetch HEAD from PR
    commit_id = config.commit_id
    if not commit_id:
        meta_resp = ctx.http.fetch(
            f"https://api.github.com/repos/{nwo}/pulls/{pr_number}",
            headers=_gh_headers(ctx),
        )
        if meta_resp.status >= 400:
            return err(f"GitHub API error {meta_resp.status}: {meta_resp.body[:500]}")
        pr_data = json.loads(meta_resp.body)
        commit_id = pr_data["head"]["sha"]

    posted, failed = _post_inline_comments(
        config.findings,
        owner,
        repo,
        pr_number,
        commit_id,
        ctx,
    )

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
        f"> {len(config.findings)} findings: {len(posted)} inline"
        + (f", {len(failed)} in summary (outside diff range)" if failed else ""),
        *_build_failed_findings_summary(failed, config.findings),
        "",
        "---",
        "",
        "*Automated review by Friday*",
    ]

    _post_review_summary(
        "\n".join(summary_parts),
        owner,
        repo,
        pr_number,
        ctx,
    )

    return ok(
        {
            "operation": "pr-inline-review",
            "success": True,
            "data": {
                "pr_number": pr_number,
                "repo": nwo,
                "posted_comments": len(posted),
                "failed_comments": len(failed),
            },
        }
    )


def _pr_post_followup(config: PrPostFollowupConfig, ctx) -> OkResult | ErrResult:
    """Post follow-up replies and new findings on a PR via GitHub REST API."""
    parts = _parse_pr_url(config.pr_url)
    owner, repo, pr_number = parts["owner"], parts["repo"], parts["pr_number"]
    nwo = f"{owner}/{repo}"

    # Post thread replies
    replies_posted = 0
    for reply in config.thread_replies or []:
        resp = ctx.http.fetch(
            f"https://api.github.com/repos/{nwo}/pulls/{pr_number}/comments/{reply['comment_id']}/replies",
            method="POST",
            headers=_gh_headers(ctx),
            body=json.dumps({"body": reply["body"]}),
        )
        if resp.status < 400:
            replies_posted += 1

    # Post new inline findings
    new_findings = config.new_findings or []
    posted: list[dict] = []
    failed: list[dict] = []

    if new_findings:
        commit_id = config.commit_id
        if not commit_id:
            meta_resp = ctx.http.fetch(
                f"https://api.github.com/repos/{nwo}/pulls/{pr_number}",
                headers=_gh_headers(ctx),
            )
            if meta_resp.status >= 400:
                return err(
                    f"GitHub API error {meta_resp.status}: {meta_resp.body[:500]}"
                )
            pr_data = json.loads(meta_resp.body)
            commit_id = pr_data["head"]["sha"]

        posted, failed = _post_inline_comments(
            new_findings,
            owner,
            repo,
            pr_number,
            commit_id,
            ctx,
        )

    # Post summary
    summary_parts = [
        "## Follow-up Review",
        "",
        config.summary,
        "",
        "---",
        "",
        f"> {replies_posted} thread replies, {len(posted)} new inline comments"
        + (f", {len(failed)} in summary" if failed else ""),
        *_build_failed_findings_summary(failed, new_findings),
        "",
        "---",
        "",
        "*Automated follow-up by Friday*",
    ]

    _post_review_summary(
        "\n".join(summary_parts),
        owner,
        repo,
        pr_number,
        ctx,
    )

    return ok(
        {
            "operation": "pr-post-followup",
            "success": True,
            "data": {
                "pr_number": pr_number,
                "repo": nwo,
                "thread_replies_posted": replies_posted,
                "new_comments_posted": len(posted),
                "failed_comments": len(failed),
            },
        }
    )


@agent(id="gh", version="1.0.0", description="GitHub PR operations agent")
def execute(prompt: str, ctx) -> OkResult | ErrResult:
    """Dispatch to operation handler based on prompt.

    Two-pass parsing: raw parse extracts operation discriminator, then
    re-parses with typed dataclass for validation. Pattern used across
    all bundled agents for type-safe operation routing.
    """
    raw = parse_input(prompt)
    operation = raw.get("operation")

    schema = _OPERATION_SCHEMAS.get(operation)
    if schema is None:
        return err(f"Unknown operation: {operation}")

    config = parse_input(prompt, schema)

    match operation:
        case "clone":
            return _clone(config, ctx)
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
