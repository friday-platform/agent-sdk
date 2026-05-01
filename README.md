# Friday Agent SDK

[![CI](https://github.com/friday-platform/agent-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/friday-platform/agent-sdk/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Write AI agents in Python (and soon other languages) that run inside the
[Friday platform](https://github.com/friday-platform/friday-studio). Agents call
LLMs, make HTTP requests, and use MCP tools through the host — no API keys or
dependencies required in agent code.

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
