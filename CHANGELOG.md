# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.7] - 2026-05-07

### Changed

- Updated the `writing-friday-python-agents` skill with Friday Studio runtime guidance for host tool usage: do not bypass `ctx.tools`, use `request_human_input` for blocking decisions, rely on injected `FRIDAY_NATS_URL`, and inspect registered agents via daemon APIs instead of hardcoded paths.

## [0.1.6] - 2026-05-07

### Added

- Added `ctx.input` structured action-input helpers for Python user agents. Agents can now read compact `inputFrom` payloads, enumerate `artifactRefs`, and hydrate JSON artifacts via host `artifacts_get` without scraping rendered prompts or re-inlining bulky upstream data.

## [0.1.5] - 2026-05-01

### Changed

- **BREAKING:** `ctx.stream.emit()` / `ctx.stream.progress()` / `ctx.stream.intent()` now publish on `agents.{sessionId}.stream` instead of `sessions.{sessionId}.events`. The previous subject was the durable JetStream session bus, so SDK chunks polluted the lifecycle replay that the host's session-detail page consumes — a strict-parse mismatch caused completed user-agent runs to render as "Running…" indefinitely. Coordinated host-side change required: atlasd must subscribe on the new subject. Bumping the daemon's `bundledAgentSDKVersion` pin to a release containing this change without the matching daemon update will silently drop all stream events.

## [0.1.4] - 2026-04-30

### Changed

- Updated the `writing-friday-python-agents` skill to register and exec agents via the daemon HTTP API (`POST /api/agents/register`, `POST /api/agents/{id}/run`) instead of the removed `atlas agent` CLI commands.

## [0.1.3] - 2026-04-30

### Changed

- Expanded the `writing-friday-python-agents` skill with a Memory section covering the platform-injected `memory_save` / `memory_read` tools: append-per-fact semantics, the read-concat-write footgun, `ToolCallError` handling, and the narrative-strategy requirement.

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
