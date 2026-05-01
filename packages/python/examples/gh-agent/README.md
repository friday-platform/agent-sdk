# gh-agent

Production-shaped GitHub PR agent. Implements the operations a code-review
agent typically needs (clone, view, diff, files, threads, post review,
inline comments, follow-ups) against the GitHub REST API.

**Demonstrates:**

- Two-pass parsing: `parse_input(prompt)` to extract the `operation`
  discriminator, then re-parse with the matching dataclass for typed config
- Bearer-token auth via `GH_TOKEN`
- Cloning a private repo without leaking the token into the URL — the token
  is fed to `git` via `GIT_ASKPASS` + `credential.helper` env vars
- Posting inline review comments and gracefully degrading to summary-only
  comments when a finding falls outside the diff range

**Required env vars:**

| Var        | Purpose                                                                |
| ---------- | ---------------------------------------------------------------------- |
| `GH_TOKEN` | GitHub personal access token (or fine-grained token) with `repo` scope |

## Operations

The prompt is JSON containing an `operation` discriminator plus operation-specific fields. All operations take a `pr_url` of the form `https://github.com/owner/repo/pull/123`.

| `operation`        | Extra fields                                                      |
| ------------------ | ----------------------------------------------------------------- |
| `clone`            | —                                                                 |
| `pr-view`          | optional `fields`                                                 |
| `pr-diff`          | optional `name_only` (bool) — return filenames only               |
| `pr-files`         | —                                                                 |
| `pr-read-threads`  | —                                                                 |
| `pr-review`        | `body` — markdown summary comment                                 |
| `pr-inline-review` | `verdict`, `summary`, `findings`, optional `commit_id`            |
| `pr-post-followup` | `summary`, optional `thread_replies`, `new_findings`, `commit_id` |

A `finding` is an object with `file`, `line`, `severity`, `category`, `title`,
`description`, and optional `start_line` / `suggestion`.

## Run it

```bash
# 1. Install the SDK (once)
pip install friday-agent-sdk

# 2. Register with your local Friday daemon
atlas agent register ./packages/python/examples/gh-agent

# 3. Execute
atlas agent exec gh '{"operation": "pr-view", "pr_url": "https://github.com/owner/repo/pull/1"}'
atlas agent exec gh '{"operation": "pr-diff", "pr_url": "https://github.com/owner/repo/pull/1", "name_only": true}'
atlas agent exec gh '{"operation": "clone", "pr_url": "https://github.com/owner/repo/pull/1"}'
```

See [`../README.md`](../README.md) for the full examples index and
[`../../README.md`](../../README.md) for the daemon quickstart.
