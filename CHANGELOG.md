# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Agent entry point changed from `_bridge.Agent` subclass to a plain `run()` function that receives the agent context as an argument. All examples and tutorials updated.
- Agent runtime switched from WASM to NATS subprocess protocol. Agents now run as native Python processes.
- Environment variables renamed for consistency:
  - `ATLAS_SESSION_ID` -> `FRIDAY_SESSION_ID`
  - `ATLAS_VALIDATE_ID` -> `FRIDAY_VALIDATE_ID`

### Added

- Capabilities are now always initialized. `ctx.llm`, `ctx.http`, `ctx.tools`, and `ctx.stream` are guaranteed available and no longer require null checks.

### Removed

- WASM build toolchain (`componentize-py`, `jco`, WIT bindings, `poll_loop.py`). Local development no longer requires compilation or Docker restarts.
