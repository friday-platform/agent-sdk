# Releasing friday-agent-sdk

Maintainer guide for cutting a new release of `friday-agent-sdk` to PyPI.

## TL;DR

```bash
git switch main && git pull
python3 scripts/bump-version.py             # bump patch (0.1.0 → 0.1.1)
# ...edit CHANGELOG.md to clean up the new section if needed...
git commit -am "chore(release): cut 0.1.1"
git push
git tag v0.1.1-test1 && git push origin v0.1.1-test1   # dry-run to TestPyPI
# ...verify on https://test.pypi.org/p/friday-agent-sdk ...
git tag v0.1.1 && git push origin v0.1.1                # real release
```

## How the pipeline works

```
            ┌──────────────────────┐
            │ scripts/bump-version │  edits 4 version files + CHANGELOG
            └──────────┬───────────┘
                       ▼
            ┌──────────────────────┐
            │ git tag + git push   │
            └──┬────────────────┬──┘
               │                │
        v*-test*                v*
               │                │
               ▼                ▼
   ┌─────────────────┐  ┌─────────────────┐
   │ release-test.yml│  │   release.yml   │
   │  → TestPyPI     │  │   → PyPI        │
   │  (env: testpypi)│  │   (env: pypi)   │
   └─────────────────┘  └─────────────────┘
```

| Component                    | Trigger                       | Publishes to | GitHub env |
| ---------------------------- | ----------------------------- | ------------ | ---------- |
| `scripts/bump-version.py`    | Manual                        | —            | —          |
| `.github/workflows/release-test.yml` | Push of `v*-test*` tag, or `workflow_dispatch` | TestPyPI | `testpypi` |
| `.github/workflows/release.yml`      | Push of `v*` tag (excl. `-test*`)              | PyPI     | `pypi`     |

Both publish workflows authenticate via **OIDC trusted publishing** — no API tokens stored anywhere.

## Prerequisites (one-time)

These have already been set up. Listed for reference if you ever need to re-create them.

### PyPI

- **Trusted Publisher:** https://pypi.org/manage/account/publishing/ (or pending publisher if project not yet created)
  - Project: `friday-agent-sdk`
  - Owner: `friday-platform`
  - Repository: `agent-sdk`
  - Workflow: `release.yml`
  - Environment: `pypi`

### TestPyPI

- **Trusted Publisher:** https://test.pypi.org/manage/account/publishing/
  - Same as PyPI, except: workflow `release-test.yml`, environment `testpypi`

### GitHub repo settings

- Environment `pypi` (Settings → Environments) restricted to tags matching `v*`
- Environment `testpypi` restricted to tags matching `v*-test*`

## Step-by-step release procedure

### 1. Bump the version

```bash
git switch main && git pull

python3 scripts/bump-version.py --dry-run     # preview the plan
python3 scripts/bump-version.py               # patch bump (default)
```

Flags:

| Flag           | Effect                                             |
| -------------- | -------------------------------------------------- |
| (none)         | Patch bump: `X.Y.Z` → `X.Y.Z+1`                    |
| `--minor`      | `X.Y.Z` → `X.Y+1.0`                                |
| `--major`      | `X.Y.Z` → `X+1.0.0`                                |
| `--set 1.2.3`  | Explicit version                                   |
| `--dry-run`    | Print plan without modifying files                 |
| `--commit`     | Also `git commit -am "chore(release): cut <new>"`  |
| `--tag`        | Implies `--commit`, also `git tag v<new>`          |
| `--push`       | Implies `--tag`, also pushes the branch and tag    |

The script edits four files in lockstep:

- `packages/python/pyproject.toml`
- `packages/python/friday_agent_sdk/__init__.py`
- `packages/python/package.json`
- `package.json`

It also moves the `## [Unreleased]` heading in `CHANGELOG.md` under a fresh `## [<new>] - YYYY-MM-DD` heading and re-adds an empty `[Unreleased]` block above it. Anything that was under `[Unreleased]` automatically becomes part of the dated release.

### 2. Edit `CHANGELOG.md`

Open the file, review what landed under the new heading, and clean it up. Aim for prose that helps a downstream user decide whether to upgrade — drop merge-bot noise, group related changes, mention breaking changes loudly.

Format follows [Keep a Changelog](https://keepachangelog.com/):

```markdown
## [0.1.1] - 2026-05-15

### Added

- `friday_agent_sdk.testing` module with `make_test_context()` and `Fake*` doubles.

### Changed

- `AgentContext` capability fields are now typed as protocols. Existing user code is unaffected at runtime; strict-mypy users may need an `isinstance` narrow when passing `ctx.llm` to a parameter typed as the concrete `Llm` class.

### Fixed

- ...
```

### 3. Commit and push

```bash
git diff                                          # last look
git commit -am "chore(release): cut 0.1.1"
git push
```

### 4. (Recommended) Dry-run to TestPyPI

Push a tag that matches `v*-test*`:

```bash
git tag v0.1.1-test1
git push origin v0.1.1-test1
```

This triggers `Release (TestPyPI dry-run)`. Watch the run at https://github.com/friday-platform/agent-sdk/actions.

When green, install from TestPyPI in a throwaway venv:

```bash
python3 -m venv /tmp/sdk-test && source /tmp/sdk-test/bin/activate
pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  friday-agent-sdk==0.1.1
python3 -c "import friday_agent_sdk; print(friday_agent_sdk.__version__)"
deactivate && rm -rf /tmp/sdk-test
```

If something's off, fix the code, commit, push, and bump the tag suffix:

```bash
git tag v0.1.1-test2
git push origin v0.1.1-test2
```

The dry-run workflow uses `skip-existing: true`, so re-running with the same in-tree version is fine.

### 5. Real release to PyPI

Once the dry-run looks good:

```bash
git tag v0.1.1
git push origin v0.1.1
```

This triggers `Release`, which:

1. Verifies the tag matches `pyproject.toml` and `friday_agent_sdk.__version__`
2. Builds the sdist + wheel with `uv build`
3. Publishes via OIDC to PyPI
4. Creates a GitHub release with the artifacts attached and auto-generated release notes

After the run finishes (~1 min), verify:

```bash
pip install friday-agent-sdk==0.1.1
```

Or visit https://pypi.org/p/friday-agent-sdk/.

## One-shot release

If you trust the pipeline and don't need a dry-run:

```bash
python3 scripts/bump-version.py --push
```

This bumps the patch, edits CHANGELOG, commits, tags `v<new>`, and pushes both. The production release workflow takes over from there.

## Troubleshooting

### `error: tag X.Y.Z != pyproject A.B.C`

The release workflow's tag-vs-version check failed. The tag you pushed doesn't match what's in `pyproject.toml` / `__init__.py`. Either:

- Re-run `bump-version.py` and re-tag with the matching version, or
- Fix the in-tree version files manually (\\don't forget all four\\) and re-tag.

### `HTTP 403: invalid-publisher` from PyPI

The Trusted Publisher configuration on PyPI doesn't match what GitHub is presenting. Verify on https://pypi.org/manage/account/publishing/ that:

- The owner/repo matches exactly (case-sensitive)
- The workflow filename matches (`release.yml` vs `release-test.yml`)
- The environment name matches (`pypi` vs `testpypi`)

### `HTTP 400: File already exists` on PyPI

You're trying to publish a version that's already on PyPI. PyPI never allows re-uploading the same `(name, version)` pair, even if you delete the release. Bump the version and retry.

This shouldn't happen on TestPyPI because `release-test.yml` sets `skip-existing: true`. If it does, double-check that flag wasn't accidentally removed.

### Workflow doesn't trigger when I push the tag

- Confirm the tag pattern matches: `v0.1.1` triggers `release.yml`; `v0.1.1-test1` triggers `release-test.yml`.
- Confirm the GitHub environment exists and its tag-policy allows your tag pattern.
- A protected branch / required-reviewers rule on the environment will pause the run waiting for approval — check the Actions tab.

### Need to undo a published version

You **can't** unpublish from PyPI in the usual sense — the file is gone but the version slot is forever taken. Yank it instead:

```bash
# Mark a release as broken; pip won't install it by default but resolved deps can still pin to it
gh release edit v0.1.1 --notes "yanked: <reason>"
# (and use the PyPI web UI: project page → Manage → Releases → Yank)
```

Then bump the patch and release a fixed version.

## Reference: where versions live

The bump script keeps these in sync. If you ever edit them by hand, all four must agree:

| File                                              | Field             |
| ------------------------------------------------- | ----------------- |
| `packages/python/pyproject.toml`                  | `project.version` |
| `packages/python/friday_agent_sdk/__init__.py`    | `__version__`     |
| `packages/python/package.json`                    | `version`         |
| `package.json`                                    | `version`         |

The release workflow checks the first two against the git tag and fails fast if they disagree.
