import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { Ajv } from "ajv";
import { beforeAll, beforeEach, describe, expect, it } from "vite-plus/test";
import { loadAgent, type LoadedAgent } from "../build/loader.ts";

const schemaPath = resolve(import.meta.dirname, "../schemas/context.schema.json");
const contextSchema = JSON.parse(readFileSync(schemaPath, "utf-8"));

const ajv = new Ajv();
const validate = ajv.compile(contextSchema);

describe("context round-trip conformance", () => {
  let agent: LoadedAgent;

  beforeAll(async () => {
    agent = await loadAgent("context-inspector");
  });

  beforeEach(() => {
    agent.stub.reset();
  });

  /**
   * Calls context-inspector's execute() and parses the result.
   * The agent returns all context fields as a JSON string in its ok payload,
   * which the bridge wraps in {"data": ...}, so we need to parse twice.
   */
  async function executeWithContext(context: Record<string, unknown>) {
    const result = await agent.agent.execute("test prompt", JSON.stringify(context));
    expect(result.tag).toBe("ok");
    const outer = JSON.parse(result.val);
    // The agent json.dumps() its result, so data is a string that needs second parsing
    return JSON.parse(outer.data);
  }

  describe("env", () => {
    it("round-trips env as Record<string, string>", async () => {
      const env = { FOO: "bar", BAZ: "qux" };
      const result = await executeWithContext({ env, config: {} });
      expect(result.env).toEqual(env);
    });

    it("round-trips empty env", async () => {
      const result = await executeWithContext({ env: {}, config: {} });
      expect(result.env).toEqual({});
    });

    it("preserves special characters in env values", async () => {
      const env = {
        SPECIAL: "hello=world&foo=bar",
        UNICODE: "\u00e9\u00e8\u00ea",
      };
      const result = await executeWithContext({ env, config: {} });
      expect(result.env).toEqual(env);
    });
  });

  describe("config", () => {
    it("round-trips flat config", async () => {
      const config = { key: "value", count: 42 };
      const result = await executeWithContext({ env: {}, config });
      expect(result.config).toEqual(config);
    });

    it("round-trips nested config objects", async () => {
      const config = {
        database: {
          host: "localhost",
          port: 5432,
          options: { ssl: true, timeout: 30 },
        },
      };
      const result = await executeWithContext({ env: {}, config });
      expect(result.config).toEqual(config);
    });

    it("round-trips config with arrays", async () => {
      const config = {
        tags: ["a", "b", "c"],
        matrix: [
          [1, 2],
          [3, 4],
        ],
      };
      const result = await executeWithContext({ env: {}, config });
      expect(result.config).toEqual(config);
    });

    it("round-trips empty config", async () => {
      const result = await executeWithContext({ env: {}, config: {} });
      expect(result.config).toEqual({});
    });
  });

  describe("session", () => {
    it("round-trips full session object", async () => {
      const session = {
        id: "sess-001",
        workspace_id: "ws-abc",
        user_id: "user-xyz",
        datetime: "2026-04-06T12:00:00Z",
      };
      const result = await executeWithContext({ env: {}, config: {}, session });
      expect(result.session).toEqual(session);
    });

    it("defaults session to null when omitted", async () => {
      const result = await executeWithContext({ env: {}, config: {} });
      expect(result.session).toBeNull();
    });

    it("passes null session explicitly", async () => {
      const result = await executeWithContext({
        env: {},
        config: {},
        session: null,
      });
      expect(result.session).toBeNull();
    });
  });

  describe("output_schema", () => {
    it("round-trips output_schema", async () => {
      const outputSchema = {
        type: "object",
        properties: { name: { type: "string" } },
        required: ["name"],
      };
      const result = await executeWithContext({
        env: {},
        config: {},
        output_schema: outputSchema,
      });
      expect(result.output_schema).toEqual(outputSchema);
    });

    it("defaults output_schema to null when omitted", async () => {
      const result = await executeWithContext({ env: {}, config: {} });
      expect(result.output_schema).toBeNull();
    });
  });

  describe("missing optional fields", () => {
    it("handles minimal context (only env and config)", async () => {
      const result = await executeWithContext({ env: {}, config: {} });
      expect(result.env).toEqual({});
      expect(result.config).toEqual({});
      expect(result.session).toBeNull();
      expect(result.output_schema).toBeNull();
    });
  });

  describe("tools integration", () => {
    it("reports tools as available via unified stub", async () => {
      const result = await executeWithContext({ env: {}, config: {} });
      expect(result.has_tools).toBe(true);
      expect(result.tool_count).toBe(2); // echo + bash from unified stub
    });
  });

  describe("schema validation", () => {
    it("input context satisfies context.schema.json", () => {
      const contexts = [
        { env: {}, config: {} },
        { env: { A: "1" }, config: { x: true }, session: null },
        {
          env: {},
          config: {},
          session: {
            id: "s1",
            workspace_id: "ws1",
            user_id: "u1",
            datetime: "2026-01-01T00:00:00Z",
          },
        },
        {
          env: {},
          config: {},
          output_schema: { type: "object" },
          llm_config: { model: "test" },
        },
      ];

      for (const ctx of contexts) {
        const valid = validate(ctx);
        if (!valid) {
          expect.fail(
            `Context ${JSON.stringify(ctx)} failed schema validation:\n${JSON.stringify(validate.errors, null, 2)}`,
          );
        }
      }
    });
  });
});
