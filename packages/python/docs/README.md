# Friday Python Agent SDK Documentation

Developer documentation for writing Friday agents in Python.

## Quick start

New to Friday agents? Start with the tutorial:

[**→ Your First Friday Agent**](tutorial/your-first-agent.md)

Build a complete agent that uses an LLM to analyze text, register it with Friday, and iterate on your design.

## How-to guides

Task-focused recipes for common patterns:

| Guide                                                        | What You'll Learn                                            |
| ------------------------------------------------------------ | ------------------------------------------------------------ |
| [Call LLMs](how-to/call-llms.md)                             | Route generation requests through Friday's provider registry |
| [Make HTTP requests](how-to/make-http-requests.md)           | Fetch data from external APIs                                |
| [Use MCP tools](how-to/use-mcp-tools.md)                     | Invoke Model Context Protocol servers                        |
| [Handle structured input](how-to/handle-structured-input.md) | Extract JSON from Friday's enriched prompts                  |
| [Stream progress](how-to/stream-progress.md)                 | Emit real-time updates to the UI                             |

## Reference

Complete API documentation:

| Document                                         | Description                                     |
| ------------------------------------------------ | ----------------------------------------------- |
| [@agent decorator](reference/agent-decorator.md) | Decorator parameters, metadata, and entry point |
| [AgentContext](reference/agent-context.md)       | Execution context and capability availability   |
| [ctx.llm](reference/llm-capability.md)           | LLM generation methods and response types       |
| [ctx.http](reference/http-capability.md)         | HTTP fetch and response handling                |
| [ctx.tools](reference/tools-capability.md)       | MCP tool listing and invocation                 |
| [ctx.stream](reference/stream-capability.md)     | Progress and intent emission                    |
| [Result types](reference/result-types.md)        | `ok()`, `err()`, and tagged union pattern       |
| [Parse utilities](reference/parse-utilities.md)  | `parse_input()` and `parse_operation()`         |

## Explanation

Understanding the architecture:

- [**How Friday Agents Work**](explanation/how-agents-work.md) — Subprocess model, host capabilities, and the registration pipeline

## Examples

Working code in [`../examples/`](../examples/):

| Example             | Shows                                                  |
| ------------------- | ------------------------------------------------------ |
| `echo-agent`        | Minimal agent — returns input unchanged                |
| `llm-http-agent`    | LLM and HTTP capability round-trips                    |
| `tools-agent`       | MCP tool listing and invocation                        |
| `time-agent`        | Real MCP server usage (time operations)                |
| `context-inspector` | All context fields and round-trip verification         |
| `jira-agent`        | Structured input parsing with operations               |
| `claude-code-agent` | Full-featured agent with fallbacks and model selection |

## Document types

This documentation follows the [Diataxis framework](https://diataxis.fr/):

- **Tutorials** — Learning by doing (one path, complete walkthrough)
- **How-to Guides** — Working to achieve goals (task-focused, assumes competence)
- **Reference** — Facts while working (austere, complete, neutral)
- **Explanation** — Learning to understand (discussion, context, trade-offs)

## Contributing

Documentation improvements welcome. Open an issue or PR in the [agent-sdk repository](https://github.com/friday-platform/agent-sdk).

---

**US English spelling used throughout.**
