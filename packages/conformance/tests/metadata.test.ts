import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { Ajv } from "ajv";
import { describe, expect, it } from "vite-plus/test";
import { agent as echoAgent } from "../../python/examples/echo-agent/agent-js/agent.js";
import { agent as toolsAgent } from "../../python/examples/tools-agent/agent-js/agent.js";
import { agent as llmHttpAgent } from "../../python/examples/llm-http-agent/agent-js/agent.js";
import { agent as contextInspector } from "../../python/examples/context-inspector/agent-js/agent.js";
import { agent as timeAgent } from "../../python/examples/time-agent/agent-js/agent.js";
import { agent as bashTestAgent } from "../../python/examples/bash-test-agent/agent-js/agent.js";

const schemaPath = resolve(import.meta.dirname, "../schemas/metadata.schema.json");
const metadataSchema = JSON.parse(readFileSync(schemaPath, "utf-8"));

const ajv = new Ajv();
const validate = ajv.compile(metadataSchema);

interface AgentModule {
  getMetadata(): string;
}

const fixtures: {
  name: string;
  agent: AgentModule;
  id: string;
  description: string;
}[] = [
  { name: "echo-agent", agent: echoAgent, id: "echo", description: "Echoes input" },
  {
    name: "tools-agent",
    agent: toolsAgent,
    id: "tools-agent",
    description: "Exercises host capabilities",
  },
  {
    name: "llm-http-agent",
    agent: llmHttpAgent,
    id: "llm-http-agent",
    description: "Exercises LLM and HTTP capabilities",
  },
  {
    name: "context-inspector",
    agent: contextInspector,
    id: "context-inspector",
    description: "Returns all context fields for verification",
  },
  {
    name: "time-agent",
    agent: timeAgent,
    id: "time-agent",
    description: "Exercises real MCP tool usage with time server",
  },
  {
    name: "bash-test-agent",
    agent: bashTestAgent,
    id: "bash-test",
    description: "Exercises bash tool through WASM",
  },
];

describe("metadata conformance", () => {
  for (const fixture of fixtures) {
    describe(fixture.name, () => {
      it("getMetadata() returns valid JSON", () => {
        const raw = fixture.agent.getMetadata();
        expect(() => JSON.parse(raw)).not.toThrow();
      });

      it("getMetadata() output satisfies metadata schema", () => {
        const meta = JSON.parse(fixture.agent.getMetadata());
        const valid = validate(meta);
        if (!valid) {
          expect.fail(`Schema validation failed:\n${JSON.stringify(validate.errors, null, 2)}`);
        }
      });

      it("has required identity fields", () => {
        const meta = JSON.parse(fixture.agent.getMetadata());
        expect(meta.id).toBe(fixture.id);
        expect(meta.version).toBe("1.0.0");
        expect(meta.description).toBe(fixture.description);
      });

      it("has expertise with examples array", () => {
        const meta = JSON.parse(fixture.agent.getMetadata());
        expect(meta.expertise).toBeDefined();
        expect(Array.isArray(meta.expertise.examples)).toBe(true);
      });
    });
  }

  describe("time-agent mcp config", () => {
    it("includes mcp field with server configuration", () => {
      const meta = JSON.parse(timeAgent.getMetadata());
      expect(meta.mcp).toBeDefined();
      expect(meta.mcp.time).toBeDefined();
      expect(meta.mcp.time.transport.type).toBe("stdio");
    });
  });
});
