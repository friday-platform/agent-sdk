# Friday Agent SDK

An open-source SDK for authoring AI agents that run in [Friday](https://github.com/atlas-ai/friday), an AI agent orchestration platform.

## What This Is

The Friday Agent SDK lets you write agents in familiar languages (starting with Python) that execute safely inside Friday's WebAssembly sandbox. Agents you build can:

- Call LLMs through the host's provider registry — no API keys in your code
- Make outbound HTTP requests through the host's fetch layer
- Invoke MCP tools configured at the workspace level
- Stream progress updates back to the user
- Return structured data, artifacts, and outline references

## Repository Structure

```
packages/
  wit/           # The WIT contract — the spec that defines host/agent boundaries
  conformance/   # Cross-language test suite for SDK implementers
  python/        # Reference Python SDK (~800 lines, zero runtime dependencies)
```

## Getting Started

See [`packages/python/README.md`](packages/python/README.md) for the Python SDK quickstart and tutorial.

## Writing Agents in Other Languages

The WIT contract in `packages/wit/agent.wit` defines the complete interface. To add a new language:

1. Implement the contract — generate bindings from the WIT file
2. Port the 10 example agents to your language
3. Run the conformance tests — passing means compatibility with Friday

## Design Principles

- **Zero runtime dependencies in the sandbox** — Pure standard library only. Complex dependencies (Pydantic, httpx, OpenAI SDK) are blocked by WASM constraints, so we provide host capabilities instead.
- **JSON over WIT records** — Schema changes happen in JSON contracts, not WIT version bumps. Only the result variant and tool definition use WIT types.
- **Host capabilities over native imports** — `ctx.llm.generate()` routes through the host's provider registry. You get the same functionality without dependency hell.
- **Build-time validation** — The daemon validates agent metadata with Zod schemas at intake. Runtime validation happens via JSON Schema in the conformance suite.

## Contributing

Agent examples, SDK ports, and documentation improvements are welcome. Open an issue before major work to align on approach.

## Licence

MIT
