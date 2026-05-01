# bb-agent

Bitbucket equivalent of [`gh-agent`](../gh-agent/) — same operation surface,
same dispatch pattern, but talking to Bitbucket Cloud's REST API v2 with its
quirks (paginated comments/diffstat, repo-create/push as separate ops).

**Demonstrates:**

- Single-pass `parse_operation(prompt, schemas)` dispatch
- Bitbucket Basic Auth (`email + API token`)
- Pagination helper for `next`-style cursors
- Cloning over HTTPS via a temporary `GIT_ASKPASS` script so the token never
  appears in URLs, argv, or files that survive the run

**Required env vars:**

| Var               | Purpose                                                                |
| ----------------- | ---------------------------------------------------------------------- |
| `BITBUCKET_EMAIL` | Atlassian account email                                                |
| `BITBUCKET_TOKEN` | API token from <https://bitbucket.org/account/settings/app-passwords/> |

## Operations

PR URLs are of the form `https://bitbucket.org/workspace/repo/pull-requests/123`.
Repo URLs are `https://bitbucket.org/workspace/repo`.

| `operation`        | Required fields                                                                                                                                                     |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `pr-view`          | `pr_url`                                                                                                                                                            |
| `pr-diff`          | `pr_url`, optional `name_only`                                                                                                                                      |
| `pr-files`         | `pr_url`                                                                                                                                                            |
| `pr-read-threads`  | `pr_url`                                                                                                                                                            |
| `pr-review`        | `pr_url`, `body`                                                                                                                                                    |
| `pr-inline-review` | `pr_url`, `verdict`, `summary`, `findings`, optional `commit_id`                                                                                                    |
| `pr-post-followup` | `pr_url`, `summary`, `thread_replies`, `new_findings`, optional `commit_id`                                                                                         |
| `pr-create`        | `repo_url`, `source_branch`, `title`, optional `destination_branch` (default `main`), `description`, `issue_key`, `summary`, `files_changed`, `close_source_branch` |
| `clone`            | `pr_url` — clones repo, checks out PR source branch                                                                                                                 |
| `repo-clone`       | `repo_url`, optional `branch`                                                                                                                                       |
| `repo-push`        | `path`, `branch`, `repo_url`                                                                                                                                        |

## Run it

```bash
# 1. Install the SDK (once)
pip install friday-agent-sdk

# 2. Register with your local Friday daemon
atlas agent register ./packages/python/examples/bb-agent

# 3. Execute
atlas agent exec bb '{"operation": "pr-view", "pr_url": "https://bitbucket.org/ws/repo/pull-requests/1"}'
atlas agent exec bb '{"operation": "repo-clone", "repo_url": "https://bitbucket.org/ws/repo", "branch": "main"}'
```

See [`../README.md`](../README.md) for the full examples index and
[`../../README.md`](../../README.md) for the daemon quickstart.
