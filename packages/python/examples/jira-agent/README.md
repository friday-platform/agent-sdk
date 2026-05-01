# jira-agent

Production-shaped Jira issue agent. Routes typed operations against the Jira
Cloud REST API v3 using `parse_operation()` — one decorator, many handlers.
Good template for any "many-operations-against-one-vendor-API" agent.

**Demonstrates:**

- `parse_operation(prompt, schemas)` — discriminator-based dispatch across
  multiple typed dataclass configs
- Basic Auth with `email + API token` (Jira's required auth flavour)
- ADF (Atlassian Document Format) round-trip: extracting plain text from
  Jira responses and converting Markdown links to ADF on writes

**Required env vars:**

| Var               | Purpose                                                                                |
| ----------------- | -------------------------------------------------------------------------------------- |
| `JIRA_SITE`       | Your Jira host, e.g. `your-company.atlassian.net`                                      |
| `JIRA_EMAIL`      | Jira account email used for Basic Auth                                                 |
| `JIRA_API_TOKEN`  | API token from <https://id.atlassian.com/manage-profile/security/api-tokens>           |

## Operations

The prompt is JSON containing an `operation` discriminator plus operation-specific
fields:

| `operation`         | Required fields                                                          |
| ------------------- | ------------------------------------------------------------------------ |
| `issue-view`        | `issue_key`                                                              |
| `issue-search`      | `jql`, optional `max_results` (max 100)                                  |
| `issue-create`      | `project_key`, `summary`, optional `description`, `issue_type`, `labels`, `priority` |
| `issue-update`      | `issue_key`, optional `summary`, `description`, `labels`, `priority`     |
| `issue-comment`     | `issue_key`, `body` (supports `[text](url)` Markdown links)              |
| `issue-transition`  | `issue_key`, `transition_name` (case-insensitive match)                  |

## Run it

```bash
# 1. Install the SDK (once)
pip install friday-agent-sdk

# 2. Register with your local Friday daemon
atlas agent register ./packages/python/examples/jira-agent

# 3. Execute
atlas agent exec jira '{"operation": "issue-view", "issue_key": "ENG-123"}'
atlas agent exec jira '{"operation": "issue-search", "jql": "project = ENG AND status = Open", "max_results": 20}'
atlas agent exec jira '{"operation": "issue-comment", "issue_key": "ENG-123", "body": "see [the docs](https://example.com)"}'
```

See [`../README.md`](../README.md) for the full examples index and
[`../../README.md`](../../README.md) for the daemon quickstart.
