# Friday Agent SDK

[![CI](https://github.com/friday-platform/agent-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/friday-platform/agent-sdk/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/friday-agent-sdk.svg?v=1)](https://pypi.org/project/friday-agent-sdk/)
[![Python versions](https://img.shields.io/pypi/pyversions/friday-agent-sdk.svg?v=1)](https://pypi.org/project/friday-agent-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Status: alpha — APIs may change.** Pin an exact version in production and
> read the [CHANGELOG](CHANGELOG.md) before upgrading.

Write AI agents in Python (and soon other languages) that run inside the
[Friday platform](https://github.com/friday-platform/friday-studio). The host
manages credentials and routes LLM, HTTP, and MCP calls on the agent's behalf,
so your agent code stays a pure Python function — no provider SDKs, no key
plumbing.

**Requirements** (the SDK is not standalone):

- Python 3.12+
- A running [Friday daemon](https://github.com/friday-platform/friday-studio)
  (provides the `atlas` CLI and the host runtime)
- An LLM provider key (Anthropic, OpenAI, or Google) configured in the daemon's
  `.env` — agents never see it directly

- **SDK reference & guides:** [`packages/python/README.md`](packages/python/README.md)
  and [`packages/python/docs/`](packages/python/docs/)
- **Examples:** [`packages/python/examples/`](packages/python/examples/) — 10
  runnable agents from minimal to production-grade
- **Friday platform docs:** https://docs.hellofriday.ai/
- **Daemon & `atlas` CLI:** [friday-platform/friday-studio](https://github.com/friday-platform/friday-studio)

## Repository layout

This is a monorepo. The product is the Python package under
[`packages/python/`](packages/python/); the TypeScript root is dev tooling
([Vite+](https://vite.plus/)) for running checks across the workspace.

## Quick start

```bash
pip install friday-agent-sdk
```

Then see [`packages/python/README.md`](packages/python/README.md) to write
and run your first agent.

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md). Security issues: see
[SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE)
