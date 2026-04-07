import { beforeEach, describe, expect, it } from "vite-plus/test";
import { agent as toolsAgent } from "../../python/examples/tools-agent/agent-js/agent.js";
import { agent as bashAgent } from "../../python/examples/bash-test-agent/agent-js/agent.js";
import { agent as timeAgent } from "../../python/examples/time-agent/agent-js/agent.js";
import { logCalls, reset, streamCalls, toolCalls } from "../stubs/capabilities-stub.js";

const contextJson = JSON.stringify({ env: {}, config: {} });

describe("tool capabilities conformance", () => {
  beforeEach(() => {
    reset();
  });

  describe("listTools", () => {
    it("returns tool definitions with name, description, inputSchema", async () => {
      const result = await toolsAgent.execute("hello", contextJson);
      expect(result.tag).toBe("ok");

      const parsed = JSON.parse(result.val);
      // tools-agent calls listTools and returns the count
      expect(parsed.tool_count).toBe(2);
    });

    it("bash-test-agent can list tools via list-tools action", async () => {
      const input = JSON.stringify({ action: "list-tools" });
      const result = await bashAgent.execute(input, contextJson);
      expect(result.tag).toBe("ok");

      const parsed = JSON.parse(result.val);
      expect(parsed.tools).toEqual(["echo", "bash"]);
    });
  });

  describe("callTool success", () => {
    it("echo tool round-trips JSON args through stub", async () => {
      const result = await toolsAgent.execute("hello", contextJson);
      expect(result.tag).toBe("ok");

      const parsed = JSON.parse(result.val);
      expect(parsed.tool_result).toEqual({
        tool: "echo",
        received: { msg: "hello" },
      });
    });

    it("stub records the callTool invocation", async () => {
      await toolsAgent.execute("hello", contextJson);

      // tools-agent calls echo tool with { msg: prompt }
      const echoCalls = toolCalls.filter((c) => c.name === "echo");
      expect(echoCalls).toHaveLength(1);
      expect(echoCalls[0].args).toEqual({ msg: "hello" });
    });
  });

  describe("callTool error", () => {
    it("host throw → SDK catches as error → agent returns err", async () => {
      const result = await toolsAgent.execute("fail:something", contextJson);
      expect(result.tag).toBe("err");
      expect(result.val).toBe("tool-not-found");
    });

    it("stub records the failed tool call", async () => {
      await toolsAgent.execute("fail:something", contextJson);

      const failCalls = toolCalls.filter((c) => c.name === "fail");
      expect(failCalls).toHaveLength(1);
      expect(failCalls[0].args).toEqual({ reason: "something" });
    });
  });

  describe("sequential multi-call", () => {
    it("stub survives multiple callTool invocations in one execution", async () => {
      // time-agent "combo" calls get_current_time then convert_time
      const result = await timeAgent.execute("combo", contextJson);
      expect(result.tag).toBe("ok");

      expect(toolCalls).toHaveLength(2);
      expect(toolCalls[0].name).toBe("get_current_time");
      expect(toolCalls[1].name).toBe("convert_time");
    });

    it("both results are captured in agent output", async () => {
      const result = await timeAgent.execute("combo", contextJson);
      const parsed = JSON.parse(result.val);

      expect(parsed.time_result).toBeDefined();
      expect(parsed.convert_result).toBeDefined();
    });
  });

  describe("error recovery", () => {
    it("failed callTool does not poison subsequent calls", async () => {
      // time-agent "bad-tool-then-now": calls nonexistent_tool (catches error),
      // then calls get_current_time successfully
      const result = await timeAgent.execute("bad-tool-then-now", contextJson);
      expect(result.tag).toBe("ok");

      const parsed = JSON.parse(result.val);
      expect(parsed.error_caught).toBeDefined();
      expect(parsed.time_result).toBeDefined();
    });

    it("stub records both calls — failed and successful", async () => {
      await timeAgent.execute("bad-tool-then-now", contextJson);

      expect(toolCalls).toHaveLength(2);
      expect(toolCalls[0].name).toBe("nonexistent_tool");
      expect(toolCalls[1].name).toBe("get_current_time");
    });
  });

  describe("log", () => {
    it("log(level, message) is captured by stub", async () => {
      await toolsAgent.execute("hello", contextJson);

      expect(logCalls.length).toBeGreaterThanOrEqual(1);
      const startLog = logCalls.find((l) => l.message.includes("tools-agent executing"));
      expect(startLog).toBeDefined();
      expect(startLog!.level).toBe(1);
      expect(startLog!.message).toContain("hello");
    });
  });

  describe("streamEmit", () => {
    it("streamEmit(eventType, data) is captured by stub", async () => {
      await toolsAgent.execute("hello", contextJson);

      expect(streamCalls.length).toBeGreaterThanOrEqual(2);
    });

    it("emits started event with prompt", async () => {
      await toolsAgent.execute("hello", contextJson);

      const started = streamCalls.find((s) => s.eventType === "started");
      expect(started).toBeDefined();
      const data = JSON.parse(started!.data);
      expect(data.prompt).toBe("hello");
    });

    it("emits completed event with tool count", async () => {
      await toolsAgent.execute("hello", contextJson);

      const completed = streamCalls.find((s) => s.eventType === "completed");
      expect(completed).toBeDefined();
      const data = JSON.parse(completed!.data);
      expect(data.tool_count).toBe(2);
    });
  });

  describe("bash tool", () => {
    it("echo command returns stdout", async () => {
      const input = JSON.stringify({ action: "echo" });
      const result = await bashAgent.execute(input, contextJson);
      expect(result.tag).toBe("ok");

      const parsed = JSON.parse(result.val);
      expect(parsed.bash_result.stdout).toBe("echo hello");
      expect(parsed.bash_result.exit_code).toBe(0);
    });

    it("non-zero exit code throws (caught by bridge as err)", async () => {
      const input = JSON.stringify({ action: "exit-code" });
      const result = await bashAgent.execute(input, contextJson);
      expect(result.tag).toBe("err");
      expect(result.val).toContain("exited with code 42");
    });

    it("stub records bash tool calls", async () => {
      const input = JSON.stringify({ action: "echo" });
      await bashAgent.execute(input, contextJson);

      const bashCalls = toolCalls.filter((c) => c.name === "bash");
      expect(bashCalls).toHaveLength(1);
      expect(bashCalls[0].args).toEqual({ command: "echo hello" });
    });
  });
});
