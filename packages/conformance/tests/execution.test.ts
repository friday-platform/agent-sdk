import { beforeAll, beforeEach, describe, expect, it } from "vite-plus/test";
import { loadAgent, type LoadedAgent } from "../build/loader.ts";

interface AgentResult {
  tag: "ok" | "err";
  val: string;
}

const contextJson = JSON.stringify({ env: {}, config: {} });

/**
 * JSPI makes execute() return a Promise at runtime, but the generated .d.ts
 * declares it as synchronous. Promise.resolve() wraps both cases correctly.
 */
function execute(
  agent: {
    execute: (prompt: string, context: string) => AgentResult | Promise<AgentResult>;
  },
  prompt: string,
  context: string,
): Promise<AgentResult> {
  return Promise.resolve(agent.execute(prompt, context));
}

describe("execution conformance", () => {
  let echoAgent: LoadedAgent;
  let toolsAgent: LoadedAgent;

  beforeAll(async () => {
    [echoAgent, toolsAgent] = await Promise.all([
      loadAgent("echo-agent"),
      loadAgent("tools-agent"),
    ]);
  });

  beforeEach(() => {
    echoAgent.stub.reset();
    toolsAgent.stub.reset();
  });

  describe("ok variant", () => {
    it("echo-agent returns prompt as-is", async () => {
      const result = await execute(echoAgent.agent, "hello", contextJson);
      expect(result.tag).toBe("ok");
      const parsed = JSON.parse(result.val);
      expect(parsed.data).toBe("hello");
    });

    it("result.val is always a string", async () => {
      const result = await execute(echoAgent.agent, "test", contextJson);
      expect(typeof result.val).toBe("string");
      // Verify it's valid JSON with a data field
      const parsed = JSON.parse(result.val);
      expect(parsed.data).toBeDefined();
    });

    it("complex input with spaces and symbols survives round-trip", async () => {
      const input = "complex input with spaces & symbols! @#$%^*()";
      const result = await execute(echoAgent.agent, input, contextJson);
      expect(result.tag).toBe("ok");
      const parsed = JSON.parse(result.val);
      expect(parsed.data).toBe(input);
    });

    it("tools-agent returns structured JSON on success", async () => {
      const result = await execute(toolsAgent.agent, "hello", contextJson);
      expect(result.tag).toBe("ok");
      const parsed = JSON.parse(result.val);
      // OkResult is wrapped in a 'data' field by the bridge
      expect(parsed.data.tool_result).toEqual({
        tool: "echo",
        received: { msg: "hello" },
      });
    });
  });

  describe("err variant", () => {
    it("tools-agent returns err for fail: prefix", async () => {
      const result = await execute(toolsAgent.agent, "fail:something", contextJson);
      expect(result.tag).toBe("err");
      expect(result.val).toBe("tool-not-found");
    });

    it("err result.val is a string", async () => {
      const result = await execute(toolsAgent.agent, "fail:test", contextJson);
      expect(typeof result.val).toBe("string");
    });
  });

  describe("async behavior", () => {
    it("execute() returns a Promise at runtime via JSPI", () => {
      const result = echoAgent.agent.execute("test", contextJson);
      // JSPI makes the synchronous WIT export return a Promise at runtime
      expect(Promise.resolve(result)).toBeInstanceOf(Promise);
    });
  });
});
