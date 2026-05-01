# Contributing to Friday Agent SDK

Thanks for your interest in contributing! This document covers everything you
need to set up a development environment, run the test suite, and submit a
pull request.

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By
participating, you agree to uphold it.

## Reporting Bugs and Requesting Features

- **Bugs:** open a [bug report](https://github.com/friday-platform/agent-sdk/issues/new?template=bug_report.yml)
  with reproduction steps and your environment details.
- **Features:** open a [feature request](https://github.com/friday-platform/agent-sdk/issues/new?template=feature_request.yml)
  describing the use case before writing code, so we can discuss the design.
- **Security issues:** see [SECURITY.md](SECURITY.md) — do not open public issues.

## Development Setup

### Prerequisites

| Tool                                                              | Version            | Why                                                               |
| ----------------------------------------------------------------- | ------------------ | ----------------------------------------------------------------- |
| [Node.js](https://nodejs.org/)                                    | `24+` (Active LTS) | Runs Vite+ tooling                                                |
| [pnpm](https://pnpm.io/)                                          | `10+`              | JS/TS package manager (managed via `packageManager` field)        |
| [Python](https://www.python.org/)                                 | `3.12+`            | Required by `friday_agent_sdk`                                    |
| [uv](https://docs.astral.sh/uv/)                                  | latest             | Python package manager                                            |
| [Vite+ (`vp`)](https://vite.plus/)                                | latest             | Unified JS/TS toolchain                                           |
| [Friday Studio](https://github.com/friday-platform/friday-studio) | latest             | Provides the daemon and `atlas` CLI for running agents end-to-end |

### Clone and install

```bash
git clone https://github.com/friday-platform/agent-sdk
cd agent-sdk

# JS/TS workspace
vp install

# Python package
cd packages/python
uv sync --all-extras --dev
```

## Running Checks

Before opening a PR, run all checks locally:

```bash
# JS/TS — lint, format, type-check, test, build
vp check
vp test

# Python
cd packages/python
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

CI runs the same checks on every pull request — see
[`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## Making Changes

1. Fork the repository and create a branch from `main`.
2. Keep changes focused — one logical change per PR.
3. Add or update tests for any behavioural change.
4. Update relevant documentation in `packages/python/docs/` if you change the
   public API.
5. Follow existing code style — `ruff` for Python, `vp fmt` for JS/TS.
6. Write a clear commit message in [Conventional Commits](https://www.conventionalcommits.org/)
   style (e.g. `feat(llm): add streaming support`).

## Submitting a Pull Request

- Use the [PR template](.github/PULL_REQUEST_TEMPLATE.md) — fill in the summary
  and test plan.
- Link any related issues with `Closes #123`.
- Make sure CI is green before requesting review.
- Be responsive to review feedback; we aim to review within a few business days.

## Project Layout

```
.
├── packages/python/         # The Python SDK (the actual product)
│   ├── friday_agent_sdk/    # Source
│   ├── tests/               # pytest suite
│   ├── examples/            # Self-contained example agents
│   └── docs/                # User-facing docs (tutorial, how-to, reference)
├── package.json             # Root workspace (dev tooling only)
├── pnpm-workspace.yaml      # pnpm + Vite+ catalog
└── .github/                 # CI, Dependabot, issue templates
```

## License

By contributing, you agree that your contributions will be licensed under the
[MIT License](LICENSE).
