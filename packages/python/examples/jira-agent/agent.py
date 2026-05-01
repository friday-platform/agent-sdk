"""Jira agent — deterministic issue operations via the Jira REST API v3.

Port of packages/bundled-agents/src/jira/agent.ts to Python.
Uses parse_operation to extract operation configs from enriched prompts,
then dispatches to handlers that call Jira API via ctx.http.

Jira REST API docs: https://developer.atlassian.com/cloud/jira/platform/rest/v3/
"""

import base64
import json
import re
from dataclasses import dataclass

from friday_agent_sdk import ErrResult, OkResult, agent, err, ok, parse_operation, run


@dataclass
class IssueViewConfig:
    operation: str
    issue_key: str


@dataclass
class IssueSearchConfig:
    operation: str
    jql: str
    max_results: int = 50


@dataclass
class IssueTransitionConfig:
    operation: str
    issue_key: str
    transition_name: str


@dataclass
class IssueCreateConfig:
    operation: str
    project_key: str
    summary: str
    description: str | None = None
    issue_type: str = "Bug"
    labels: list[str] | None = None
    priority: str | None = None


@dataclass
class IssueUpdateConfig:
    operation: str
    issue_key: str
    summary: str | None = None
    description: str | None = None
    labels: list[str] | None = None
    priority: str | None = None


@dataclass
class IssueCommentConfig:
    operation: str
    issue_key: str
    body: str


# Map operation name to its typed config dataclass
_OPERATION_SCHEMAS: dict[str, type] = {
    "issue-view": IssueViewConfig,
    "issue-search": IssueSearchConfig,
    "issue-transition": IssueTransitionConfig,
    "issue-create": IssueCreateConfig,
    "issue-update": IssueUpdateConfig,
    "issue-comment": IssueCommentConfig,
}


def _extract_adf_text(adf) -> str:
    """Recursively extract plain text from ADF document."""
    if adf is None:
        return ""
    if isinstance(adf, str):
        return adf
    texts = []
    if isinstance(adf, dict):
        if adf.get("type") == "text":
            texts.append(adf.get("text", ""))
        for child in adf.get("content", []):
            texts.append(_extract_adf_text(child))
    return "".join(texts)


def _text_to_adf(text: str) -> dict:
    """Convert plain text to minimal ADF (Atlassian Document Format).

    ADF is Jira's rich text format. Supports [text](url) markdown links.
    See: https://developer.atlassian.com/cloud/jira/platform/apis/document/structure/
    """
    content = []
    parts = re.split(
        r"\[([^\]]+)\]\(([^()]*(?:\([^()]*\)[^()]*)*)\)",
        text,
    )
    for i, part in enumerate(parts):
        if i % 3 == 0:
            if part:
                content.append({"type": "text", "text": part})
        elif i % 3 == 1:
            link_text = part
            link_url = parts[i + 1]
            content.append(
                {
                    "type": "text",
                    "text": link_text,
                    "marks": [
                        {
                            "type": "link",
                            "attrs": {"href": link_url},
                        }
                    ],
                }
            )

    return {
        "type": "doc",
        "version": 1,
        "content": ([{"type": "paragraph", "content": content}] if content else []),
    }


def _build_auth_header(ctx) -> str:
    """Build Basic Auth header from JIRA_EMAIL and JIRA_API_TOKEN.

    Jira uses email + API token (not password) for Basic Auth.
    See: https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/
    """
    email = ctx.env.get("JIRA_EMAIL", "")
    token = ctx.env.get("JIRA_API_TOKEN", "")
    credentials = base64.b64encode(f"{email}:{token}".encode()).decode()
    return f"Basic {credentials}"


def _issue_view(config: IssueViewConfig, ctx) -> OkResult | ErrResult:
    """Jira API v3: GET /rest/api/3/issue/{key}"""
    site = ctx.env.get("JIRA_SITE", "")
    url = f"https://{site}/rest/api/3/issue/{config.issue_key}"

    response = ctx.http.fetch(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "friday-jira-agent",
            "Authorization": _build_auth_header(ctx),
        },
    )

    # 500 char limit — Jira error responses can be verbose HTML
    if response.status >= 400:
        return err(f"Jira API error {response.status}: {response.body[:500]}")

    data = json.loads(response.body)
    fields = data.get("fields", {})
    return ok(
        {
            "operation": "issue-view",
            "success": True,
            "data": {
                "key": data.get("key"),
                "id": data.get("id"),
                "summary": fields.get("summary"),
                "description": _extract_adf_text(fields.get("description")),
                "status": fields.get("status", {}).get("name"),
                "priority": fields.get("priority", {}).get("name"),
                "issue_type": fields.get("issuetype", {}).get("name"),
                "labels": fields.get("labels", []),
                "assignee": (fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None),
                "reporter": (fields.get("reporter", {}).get("displayName") if fields.get("reporter") else None),
                "created": fields.get("created"),
                "updated": fields.get("updated"),
            },
        }
    )


_SEARCH_FIELDS = [
    "summary",
    "status",
    "priority",
    "issuetype",
    "labels",
    "assignee",
    "reporter",
    "description",
    "created",
    "updated",
]


def _issue_search(
    config: IssueSearchConfig,
    ctx,
) -> OkResult | ErrResult:
    """Jira API v3: POST /rest/api/3/search/jql — JQL query endpoint."""
    site = ctx.env.get("JIRA_SITE", "")
    url = f"https://{site}/rest/api/3/search/jql"
    # Jira maxResults capped at 100 — higher values silently ignored
    capped = min(config.max_results, 100)

    body = json.dumps(
        {
            "jql": config.jql,
            "maxResults": capped,
            "fields": _SEARCH_FIELDS,
        }
    )

    response = ctx.http.fetch(
        url,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "friday-jira-agent",
            "Authorization": _build_auth_header(ctx),
        },
        body=body,
    )

    if response.status >= 400:
        return err(f"Jira API error {response.status}: {response.body[:500]}")

    data = json.loads(response.body)
    issues = []
    for issue in data.get("issues", []):
        fields = issue.get("fields", {})
        priority = fields.get("priority")
        issues.append(
            {
                "key": issue["key"],
                "summary": fields.get("summary"),
                "status": fields.get("status", {}).get("name"),
                "priority": (priority.get("name") if priority else None),
                "issue_type": (fields.get("issuetype", {}).get("name")),
                "labels": fields.get("labels", []),
            }
        )

    return ok(
        {
            "operation": "issue-search",
            "success": True,
            "data": {
                "issues": issues,
                "count": len(issues),
                "is_last": data.get("isLast", True),
                "max_results": capped,
            },
        }
    )


def _issue_transition(
    config: IssueTransitionConfig,
    ctx,
) -> OkResult | ErrResult:
    """Transition a Jira issue to a new status.

    1. GET available transitions
    2. Case-insensitive match transition_name
    3. POST the transition
    """
    site = ctx.env.get("JIRA_SITE", "")
    base = f"https://{site}/rest/api/3/issue/{config.issue_key}"
    auth_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "friday-jira-agent",
        "Authorization": _build_auth_header(ctx),
    }

    # 1. Get available transitions
    resp = ctx.http.fetch(
        f"{base}/transitions",
        headers=auth_headers,
    )
    if resp.status >= 400:
        return err(f"Jira API error {resp.status}: {resp.body[:500]}")

    transitions = json.loads(resp.body).get("transitions", [])
    target = config.transition_name.lower()
    matched = None
    for t in transitions:
        if t.get("name", "").lower() == target:
            matched = t
            break

    if matched is None:
        available = [t.get("name", "") for t in transitions]
        return err(
            f"No transition matching '{config.transition_name}' for {config.issue_key}. Available: {', '.join(available)}"
        )

    # 2. Execute transition
    resp = ctx.http.fetch(
        f"{base}/transitions",
        method="POST",
        headers=auth_headers,
        body=json.dumps({"transition": {"id": matched["id"]}}),
    )
    if resp.status >= 400:
        return err(f"Jira API error {resp.status}: {resp.body[:500]}")

    return ok(
        {
            "operation": "issue-transition",
            "success": True,
            "data": {
                "issue_key": config.issue_key,
                "to_status": matched["name"],
            },
        }
    )


def _issue_create(
    config: IssueCreateConfig,
    ctx,
) -> OkResult | ErrResult:
    """Jira API v3: POST /rest/api/3/issue"""
    site = ctx.env.get("JIRA_SITE", "")
    url = f"https://{site}/rest/api/3/issue"

    fields: dict = {
        "project": {"key": config.project_key},
        "summary": config.summary,
        "issuetype": {"name": config.issue_type},
    }
    if config.description:
        fields["description"] = _text_to_adf(config.description)
    if config.labels:
        fields["labels"] = config.labels
    if config.priority:
        fields["priority"] = {"name": config.priority}

    response = ctx.http.fetch(
        url,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "friday-jira-agent",
            "Authorization": _build_auth_header(ctx),
        },
        body=json.dumps({"fields": fields}),
    )

    if response.status >= 400:
        return err(f"Jira API error {response.status}: {response.body[:500]}")

    data = json.loads(response.body)
    return ok(
        {
            "operation": "issue-create",
            "success": True,
            "data": {
                "key": data.get("key"),
                "id": data.get("id"),
                "self": data.get("self"),
            },
        }
    )


def _issue_update(
    config: IssueUpdateConfig,
    ctx,
) -> OkResult | ErrResult:
    """Jira API v3: PUT /rest/api/3/issue/{key}"""
    site = ctx.env.get("JIRA_SITE", "")
    url = f"https://{site}/rest/api/3/issue/{config.issue_key}"

    fields: dict = {}
    if config.summary is not None:
        fields["summary"] = config.summary
    if config.description is not None:
        fields["description"] = _text_to_adf(config.description)
    if config.labels is not None:
        fields["labels"] = config.labels
    if config.priority is not None:
        fields["priority"] = {"name": config.priority}

    response = ctx.http.fetch(
        url,
        method="PUT",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "friday-jira-agent",
            "Authorization": _build_auth_header(ctx),
        },
        body=json.dumps({"fields": fields}),
    )

    if response.status >= 400:
        return err(f"Jira API error {response.status}: {response.body[:500]}")

    return ok(
        {
            "operation": "issue-update",
            "success": True,
            "data": {
                "issue_key": config.issue_key,
                "updated": True,
            },
        }
    )


def _issue_comment(
    config: IssueCommentConfig,
    ctx,
) -> OkResult | ErrResult:
    """Jira API v3: POST /rest/api/3/issue/{key}/comment"""
    site = ctx.env.get("JIRA_SITE", "")
    url = f"https://{site}/rest/api/3/issue/{config.issue_key}/comment"

    response = ctx.http.fetch(
        url,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "friday-jira-agent",
            "Authorization": _build_auth_header(ctx),
        },
        body=json.dumps({"body": _text_to_adf(config.body)}),
    )

    if response.status >= 400:
        return err(f"Jira API error {response.status}: {response.body[:500]}")

    data = json.loads(response.body)
    return ok(
        {
            "operation": "issue-comment",
            "success": True,
            "data": {
                "issue_key": config.issue_key,
                "comment_id": str(data.get("id", "")),
            },
        }
    )


@agent(id="jira", version="1.0.0", description="Jira issue operations agent")
def execute(prompt: str, ctx):
    """Dispatch to operation handler based on prompt.

    Single-pass parsing with discriminator: parse_operation() filters to
    JSON containing "operation", selects schema, validates in one step.
    """
    try:
        config = parse_operation(prompt, _OPERATION_SCHEMAS)
    except ValueError as e:
        return err(str(e))

    operation = config.operation

    match operation:
        case "issue-view":
            return _issue_view(config, ctx)
        case "issue-search":
            return _issue_search(config, ctx)
        case "issue-transition":
            return _issue_transition(config, ctx)
        case "issue-create":
            return _issue_create(config, ctx)
        case "issue-update":
            return _issue_update(config, ctx)
        case "issue-comment":
            return _issue_comment(config, ctx)


if __name__ == "__main__":
    run()
