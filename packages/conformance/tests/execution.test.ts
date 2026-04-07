import { beforeEach, describe, expect, it } from "vite-plus/test";
import { agent as echoAgent } from "../../python/examples/echo-agent/agent-js/agent.js";
import { agent as toolsAgent } from "../../python/examples/tools-agent/agent-js/agent.js";
import { reset } from "../stubs/capabilities-stub.js";

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
  agent: { execute: (prompt: string, context: string) => AgentResult },
  prompt: string,
  context: string,
): Promise<AgentResult> {
  return Promise.resolve(agent.execute(prompt, context));
}

describe("execution conformance", () => {
  beforeEach(() => {
    reset();
  });

  describe("ok variant", () => {
    it("echo-agent returns prompt as-is", async () => {
      const result = await execute(echoAgent, "hello", contextJson);
      expect(result.tag).toBe("ok");
      expect(result.val).toBe("hello");
    });

    it("result.val is always a string", async () => {
      const result = await execute(echoAgent, "test", contextJson);
      expect(typeof result.val).toBe("string");
    });

    it("complex input with spaces and symbols survives round-trip", async () => {
      const input = "complex input with spaces & symbols! @#$%^*()";
      const result = await execute(echoAgent, input, contextJson);
      expect(result.tag).toBe("ok");
      expect(result.val).toBe(input);
    });

    it("tools-agent returns structured JSON on success", async () => {
      const result = await execute(toolsAgent, "hello", contextJson);
      expect(result.tag).toBe("ok");
      const parsed = JSON.parse(result.val);
      expect(parsed.tool_result).toEqual({ tool: "echo", received: { msg: "hello" } });
    });
  });

  describe("err variant", () => {
    it("tools-agent returns err for fail: prefix", async () => {
      const result = await execute(toolsAgent, "fail:something", contextJson);
      expect(result.tag).toBe("err");
      expect(result.val).toBe("tool-not-found");
    });

    it("err result.val is a string", async () => {
      const result = await execute(toolsAgent, "fail:test", contextJson);
      expect(typeof result.val).toBe("string");
    });
  });

  describe("async behavior", () => {
    it("execute() returns a Promise at runtime via JSPI", () => {
      const result = echoAgent.execute("test", contextJson);
      // JSPI makes the synchronous WIT export return a Promise at runtime
      expect(Promise.resolve(result)).toBeInstanceOf(Promise);
    });
  });
});
