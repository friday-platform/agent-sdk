# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.2] - 2026-04-30

### Changed

- Tightened the `writing-friday-python-agents` skill description so it loads only when authoring a user agent is already the task, not when deciding whether to author one.

### Added

- `RELEASING.md` maintainer guide covering the bump-version + tag-driven TestPyPI/PyPI release flow.

## [0.1.1] - 2026-04-30

### Fixed

- ReDoS in `jira-agent` markdown link regex.

### Added

- `scripts/bump-version.py` for synchronized version bumps across the SDK and examples.
- TestPyPI dry-run release workflow.
- READMEs for each example agent (`echo-agent`, `llm-http-agent`, `jira-agent`).
- mypy type-checking and built-wheel smoke test in CI.
- Real-NATS round-trip tests covering `build_context` end-to-end (alongside the existing mocked tests).
- Alpha banner and CI/PyPI/license badges in the top-level README; clarified that the SDK requires a running Friday daemon.

### Changed

- Broadened ruff ruleset and applied autofixes across the Python package.
- Bumped pinned `nats-server` in CI to v2.14.0.

## [0.1.0] - 2026-04-30

Initial public release. **Alpha — APIs may change.**

### Changed

- Agent entry point changed from `_bridge.Agent` subclass to a plain `run()` function that receives the agent context as an argument. All examples and tutorials updated.
- Agent runtime switched from WASM to NATS subprocess protocol. Agents now run as native Python processes.
- Environment variables renamed for consistency:
  - `ATLAS_SESSION_ID` -> `FRIDAY_SESSION_ID`
  - `ATLAS_VALIDATE_ID` -> `FRIDAY_VALIDATE_ID`

### Added

- `friday_agent_sdk.__version__` exported for runtime introspection.
- Capabilities are now always initialized. `ctx.llm`, `ctx.http`, `ctx.tools`, and `ctx.stream` are guaranteed available and no longer require null checks.

### Removed

- WASM build toolchain (`componentize-py`, `jco`, WIT bindings, `poll_loop.py`). Local development no longer requires compilation or Docker restarts.
