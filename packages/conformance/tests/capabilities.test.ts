import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { Ajv } from "ajv";
import { beforeEach, describe, expect, it } from "vite-plus/test";
import { agent } from "../../python/examples/llm-http-agent/agent-js/agent.js";
import { httpCalls, llmCalls, logCalls, reset } from "../stubs/capabilities-stub.js";

const contextJson = JSON.stringify({ env: {}, config: {} });

const ajv = new Ajv({ strict: false });

function loadSchema(name: string) {
  const path = resolve(import.meta.dirname, `../schemas/${name}`);
  return ajv.compile(JSON.parse(readFileSync(path, "utf-8")));
}

const validateLlmRequest = loadSchema("llm-request.schema.json");
const validateLlmResponse = loadSchema("llm-response.schema.json");
const validateHttpRequest = loadSchema("http-request.schema.json");
const validateHttpResponse = loadSchema("http-response.schema.json");

describe("LLM capabilities conformance", () => {
  beforeEach(() => {
    reset();
  });

  describe("request serialization", () => {
    it("sends model and messages through the WIT boundary", async () => {
      await agent.execute("llm:hello", contextJson);

      expect(llmCalls).toHaveLength(1);
      const req = llmCalls[0] as Record<string, unknown>;
      expect(req.model).toBe("test-model");
      expect(req.messages).toEqual([{ role: "user", content: "hello" }]);
    });

    it("request conforms to llm-request schema", async () => {
      await agent.execute("llm:test", contextJson);

      const req = llmCalls[0];
      const valid = validateLlmRequest(req);
      if (!valid) {
        expect.fail(
          `LLM request schema validation failed:\n${JSON.stringify(validateLlmRequest.errors, null, 2)}`,
        );
      }
    });

    it("model field is optional (host resolves from config)", async () => {
      // The llm-request schema has model as optional
      const schemaPath = resolve(import.meta.dirname, "../schemas/llm-request.schema.json");
      const schema = JSON.parse(readFileSync(schemaPath, "utf-8"));
      const required = schema.required as string[];
      expect(required).not.toContain("model");
    });
  });

  describe("response parsing", () => {
    it("text response flows back through WIT to agent", async () => {
      const result = await agent.execute("llm:hello", contextJson);

      expect(result.tag).toBe("ok");
      const parsed = JSON.parse(result.val);
      expect(parsed.llm_result.text).toBe("mock response");
      expect(parsed.llm_result.model).toBe("test-model");
      expect(parsed.llm_result.finish_reason).toBe("stop");
    });

    it("stub response conforms to llm-response schema", async () => {
      // Validate the shape the stub returns (what the SDK must parse)
      const stubResponse = {
        text: "mock response",
        object: null,
        model: "test-model",
        usage: { prompt_tokens: 10, completion_tokens: 5 },
        finish_reason: "stop",
      };
      const valid = validateLlmResponse(stubResponse);
      if (!valid) {
        expect.fail(
          `LLM response schema validation failed:\n${JSON.stringify(validateLlmResponse.errors, null, 2)}`,
        );
      }
    });

    it("usage contains prompt_tokens and completion_tokens", () => {
      // Verify schema requires usage fields
      const schemaPath = resolve(import.meta.dirname, "../schemas/llm-response.schema.json");
      const schema = JSON.parse(readFileSync(schemaPath, "utf-8"));
      const usageRequired = schema.properties.usage.required as string[];
      expect(usageRequired).toContain("prompt_tokens");
      expect(usageRequired).toContain("completion_tokens");
    });
  });

  describe("error path", () => {
    it("host throw propagates as err variant", async () => {
      const result = await agent.execute("llm-fail:something", contextJson);

      expect(result.tag).toBe("err");
      expect(result.val).toBe("llm-unavailable");
    });
  });

  describe("provider_options passthrough", () => {
    it("schema allows provider_options as an object", () => {
      const schemaPath = resolve(import.meta.dirname, "../schemas/llm-request.schema.json");
      const schema = JSON.parse(readFileSync(schemaPath, "utf-8"));
      expect(schema.properties.provider_options).toBeDefined();
      expect(schema.properties.provider_options.type).toBe("object");
    });

    it("request with provider_options validates against schema", () => {
      const req = {
        messages: [{ role: "user", content: "test" }],
        model: "test-model",
        provider_options: { custom_key: "custom_value", nested: { a: 1 } },
      };
      const valid = validateLlmRequest(req);
      if (!valid) {
        expect.fail(
          `Schema validation failed:\n${JSON.stringify(validateLlmRequest.errors, null, 2)}`,
        );
      }
    });
  });
});

describe("HTTP capabilities conformance", () => {
  beforeEach(() => {
    reset();
  });

  describe("request serialization", () => {
    it("sends url and method through the WIT boundary", async () => {
      await agent.execute("http:test-path", contextJson);

      expect(httpCalls).toHaveLength(1);
      const req = httpCalls[0] as Record<string, unknown>;
      expect(req.url).toBe("https://example.com/test-path");
      expect(req.method).toBe("GET");
    });

    it("request conforms to http-request schema", async () => {
      await agent.execute("http:api/data", contextJson);

      const req = httpCalls[0];
      const valid = validateHttpRequest(req);
      if (!valid) {
        expect.fail(
          `HTTP request schema validation failed:\n${JSON.stringify(validateHttpRequest.errors, null, 2)}`,
        );
      }
    });

    it("method defaults to GET", async () => {
      // The Python SDK defaults method to "GET"
      await agent.execute("http:test", contextJson);

      const req = httpCalls[0] as Record<string, unknown>;
      expect(req.method).toBe("GET");
    });
  });

  describe("response parsing", () => {
    it("status and body flow back through WIT to agent", async () => {
      const result = await agent.execute("http:test", contextJson);

      expect(result.tag).toBe("ok");
      const parsed = JSON.parse(result.val);
      expect(parsed.http_result.status).toBe(200);
      expect(JSON.parse(parsed.http_result.body)).toEqual({
        ok: true,
        url: "https://example.com/test",
      });
    });

    it("stub response conforms to http-response schema", () => {
      const stubResponse = {
        status: 200,
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ ok: true, url: "https://example.com/test" }),
      };
      const valid = validateHttpResponse(stubResponse);
      if (!valid) {
        expect.fail(
          `HTTP response schema validation failed:\n${JSON.stringify(validateHttpResponse.errors, null, 2)}`,
        );
      }
    });
  });

  describe("error path", () => {
    it("host throw propagates as err variant", async () => {
      const result = await agent.execute("http-fail:something", contextJson);

      expect(result.tag).toBe("err");
      expect(result.val).toBe("connection-refused");
    });
  });

  describe("request schema completeness", () => {
    it("schema supports headers, body, and timeout_ms fields", () => {
      const schemaPath = resolve(import.meta.dirname, "../schemas/http-request.schema.json");
      const schema = JSON.parse(readFileSync(schemaPath, "utf-8"));
      expect(schema.properties.headers).toBeDefined();
      expect(schema.properties.body).toBeDefined();
      expect(schema.properties.timeout_ms).toBeDefined();
    });

    it("full request with all optional fields validates against schema", () => {
      const req = {
        url: "https://example.com/api",
        method: "POST",
        headers: { "content-type": "application/json", authorization: "Bearer token" },
        body: '{"key":"value"}',
        timeout_ms: 5000,
      };
      const valid = validateHttpRequest(req);
      if (!valid) {
        expect.fail(
          `Schema validation failed:\n${JSON.stringify(validateHttpRequest.errors, null, 2)}`,
        );
      }
    });
  });
});

describe("logging from capabilities agent", () => {
  beforeEach(() => {
    reset();
  });

  it("log calls from agent reach the host", async () => {
    await agent.execute("llm:hello", contextJson);

    expect(logCalls.length).toBeGreaterThan(0);
    expect(logCalls[0]?.message).toContain("llm-http-agent executing: llm:hello");
  });
});
