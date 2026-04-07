import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { Ajv } from "ajv";
import { describe, expect, it } from "vite-plus/test";
import { agent } from "../../python/examples/echo-agent/agent-js/agent.js";

const schemaPath = resolve(import.meta.dirname, "../schemas/metadata.schema.json");
const metadataSchema = JSON.parse(readFileSync(schemaPath, "utf-8"));

const ajv = new Ajv();
const validate = ajv.compile(metadataSchema);

describe("metadata conformance", () => {
  it("getMetadata() returns valid JSON", () => {
    const raw = agent.getMetadata();
    expect(() => JSON.parse(raw)).not.toThrow();
  });

  it("getMetadata() output satisfies metadata schema", () => {
    const meta = JSON.parse(agent.getMetadata());
    const valid = validate(meta);
    if (!valid) {
      expect.fail(`Schema validation failed:\n${JSON.stringify(validate.errors, null, 2)}`);
    }
  });

  it("has required identity fields", () => {
    const meta = JSON.parse(agent.getMetadata());
    expect(meta.id).toBe("echo");
    expect(meta.version).toBe("1.0.0");
    expect(meta.description).toBe("Echoes input");
  });

  it("has expertise with examples array", () => {
    const meta = JSON.parse(agent.getMetadata());
    expect(meta.expertise).toBeDefined();
    expect(Array.isArray(meta.expertise.examples)).toBe(true);
  });
});
