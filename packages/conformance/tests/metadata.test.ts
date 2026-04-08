import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { Ajv } from "ajv";
import { beforeAll, describe, expect, it } from "vite-plus/test";
import { loadAgent, type LoadedAgent } from "../build/loader.ts";

const schemaPath = resolve(import.meta.dirname, "../schemas/metadata.schema.json");
const metadataSchema = JSON.parse(readFileSync(schemaPath, "utf-8"));

const ajv = new Ajv();
const validate = ajv.compile(metadataSchema);

interface Fixture {
  name: string;
  agent: LoadedAgent;
  id: string;
  description: string;
}

describe("metadata conformance", () => {
  const fixturesConfig: Array<{
    name: string;
    id: string;
    description: string;
  }> = [
    { name: "echo-agent", id: "echo", description: "Echoes input" },
    {
      name: "tools-agent",
      id: "tools-agent",
      description: "Exercises host capabilities",
    },
    {
      name: "llm-http-agent",
      id: "llm-http-agent",
      description: "Exercises LLM and HTTP capabilities",
    },
    {
      name: "context-inspector",
      id: "context-inspector",
      description: "Returns all context fields for verification",
    },
    {
      name: "time-agent",
      id: "time-agent",
      description: "Exercises real MCP tool usage with time server",
    },
    {
      name: "bash-test-agent",
      id: "bash-test",
      description: "Exercises bash tool through WASM",
    },
  ];

  const fixtures: Fixture[] = [];
  let timeAgent: LoadedAgent;

  beforeAll(async () => {
    for (const f of fixturesConfig) {
      const agent = await loadAgent(f.name);
      fixtures.push({ ...f, agent });
      if (f.name === "time-agent") {
        timeAgent = agent;
      }
    }
  });

  for (const fixture of fixturesConfig) {
    describe(fixture.name, () => {
      it("getMetadata() returns valid JSON", () => {
        const f = fixtures.find((x) => x.name === fixture.name)!;
        const raw = f.agent.agent.getMetadata();
        expect(() => JSON.parse(raw)).not.toThrow();
      });

      it("getMetadata() output satisfies metadata schema", () => {
        const f = fixtures.find((x) => x.name === fixture.name)!;
        const meta = JSON.parse(f.agent.agent.getMetadata());
        const valid = validate(meta);
        if (!valid) {
          expect.fail(`Schema validation failed:\\n${JSON.stringify(validate.errors, null, 2)}`);
        }
      });

      it("has required identity fields", () => {
        const f = fixtures.find((x) => x.name === fixture.name)!;
        const meta = JSON.parse(f.agent.agent.getMetadata());
        expect(meta.id).toBe(fixture.id);
        expect(meta.version).toBe("1.0.0");
        expect(meta.description).toBe(fixture.description);
      });

      it("has expertise with examples array", () => {
        const f = fixtures.find((x) => x.name === fixture.name)!;
        const meta = JSON.parse(f.agent.agent.getMetadata());
        expect(meta.expertise).toBeDefined();
        expect(Array.isArray(meta.expertise.examples)).toBe(true);
      });
    });
  }

  describe("time-agent mcp config", () => {
    it("includes mcp field with server configuration", () => {
      const meta = JSON.parse(timeAgent.agent.getMetadata());
      expect(meta.mcp).toBeDefined();
      expect(meta.mcp.time).toBeDefined();
      expect(meta.mcp.time.transport.type).toBe("stdio");
    });
  });
});
