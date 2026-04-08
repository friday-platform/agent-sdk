import { beforeAll, beforeEach, describe, expect, it } from "vite-plus/test";
import { loadAgent, type LoadedAgent } from "../build/loader.ts";

const contextJson = JSON.stringify({ env: {}, config: {} });

describe("tool capabilities conformance", () => {
  let toolsAgent: LoadedAgent;
  let bashAgent: LoadedAgent;
  let timeAgent: LoadedAgent;

  beforeAll(async () => {
    [toolsAgent, bashAgent, timeAgent] = await Promise.all([
      loadAgent("tools-agent"),
      loadAgent("bash-test-agent"),
      loadAgent("time-agent"),
    ]);
  });

  beforeEach(() => {
    toolsAgent.stub.reset();
    bashAgent.stub.reset();
    timeAgent.stub.reset();
  });

  describe("listTools", () => {
    it("returns tool definitions with name, description, inputSchema", async () => {
      const result = await toolsAgent.agent.execute("hello", contextJson);
      expect(result.tag).toBe("ok");

      const parsed = JSON.parse(result.val);
      // tools-agent calls listTools and returns the count
      expect(parsed.data.tool_count).toBe(2);
    });

    it("bash-test-agent can list tools via list-tools action", async () => {
      const input = JSON.stringify({ action: "list-tools" });
      const result = await bashAgent.agent.execute(input, contextJson);
      expect(result.tag).toBe("ok");

      const parsed = JSON.parse(result.val);
      expect(parsed.data.tools).toEqual(["echo", "bash"]);
    });
  });

  describe("callTool success", () => {
    it("echo tool round-trips JSON args through stub", async () => {
      const result = await toolsAgent.agent.execute("hello", contextJson);
      expect(result.tag).toBe("ok");

      const parsed = JSON.parse(result.val);
      expect(parsed.data.tool_result).toEqual({
        tool: "echo",
        received: { msg: "hello" },
      });
    });

    it("stub records the callTool invocation", async () => {
      await toolsAgent.agent.execute("hello", contextJson);

      // tools-agent calls echo tool with { msg: prompt }
      const echoCalls = toolsAgent.stub.toolCalls.filter((c) => c.name === "echo");
      expect(echoCalls).toHaveLength(1);
      expect(echoCalls[0].args).toEqual({ msg: "hello" });
    });
  });

  describe("callTool error", () => {
    it("host throw → SDK catches as error → agent returns err", async () => {
      const result = await toolsAgent.agent.execute("fail:something", contextJson);
      expect(result.tag).toBe("err");
      expect(result.val).toBe("tool-not-found");
    });

    it("stub records the failed tool call", async () => {
      await toolsAgent.agent.execute("fail:something", contextJson);

      const failCalls = toolsAgent.stub.toolCalls.filter((c) => c.name === "fail");
      expect(failCalls).toHaveLength(1);
      expect(failCalls[0].args).toEqual({ reason: "something" });
    });
  });

  describe("sequential multi-call", () => {
    it("stub survives multiple callTool invocations in one execution", async () => {
      // time-agent "combo" calls get_current_time then convert_time
      const result = await timeAgent.agent.execute("combo", contextJson);
      expect(result.tag).toBe("ok");

      expect(timeAgent.stub.toolCalls).toHaveLength(2);
      expect(timeAgent.stub.toolCalls[0].name).toBe("get_current_time");
      expect(timeAgent.stub.toolCalls[1].name).toBe("convert_time");
    });

    it("both results are captured in agent output", async () => {
      const result = await timeAgent.agent.execute("combo", contextJson);
      const parsed = JSON.parse(result.val);

      expect(parsed.data.time_result).toBeDefined();
      expect(parsed.data.convert_result).toBeDefined();
    });
  });

  describe("error recovery", () => {
    it("failed callTool does not poison subsequent calls", async () => {
      // time-agent "bad-tool-then-now": calls nonexistent_tool (catches error),
      // then calls get_current_time successfully
      const result = await timeAgent.agent.execute("bad-tool-then-now", contextJson);
      expect(result.tag).toBe("ok");

      const parsed = JSON.parse(result.val);
      expect(parsed.data.error_caught).toBeDefined();
      expect(parsed.data.time_result).toBeDefined();
    });

    it("stub records both calls — failed and successful", async () => {
      await timeAgent.agent.execute("bad-tool-then-now", contextJson);

      expect(timeAgent.stub.toolCalls).toHaveLength(2);
      expect(timeAgent.stub.toolCalls[0].name).toBe("nonexistent_tool");
      expect(timeAgent.stub.toolCalls[1].name).toBe("get_current_time");
    });
  });

  describe("log", () => {
    it("log(level, message) is captured by stub", async () => {
      await toolsAgent.agent.execute("hello", contextJson);

      expect(toolsAgent.stub.logCalls.length).toBeGreaterThanOrEqual(1);
      const startLog = toolsAgent.stub.logCalls.find((l) =>
        l.message.includes("tools-agent executing"),
      );
      expect(startLog).toBeDefined();
      expect(startLog!.level).toBe(1);
      expect(startLog!.message).toContain("hello");
    });
  });

  describe("streamEmit", () => {
    it("streamEmit(eventType, data) is captured by stub", async () => {
      await toolsAgent.agent.execute("hello", contextJson);

      expect(toolsAgent.stub.streamCalls.length).toBeGreaterThanOrEqual(2);
    });

    it("emits started event with prompt", async () => {
      await toolsAgent.agent.execute("hello", contextJson);

      const started = toolsAgent.stub.streamCalls.find((s) => s.eventType === "started");
      expect(started).toBeDefined();
      const data = JSON.parse(started!.data);
      expect(data.prompt).toBe("hello");
    });

    it("emits completed event with tool count", async () => {
      await toolsAgent.agent.execute("hello", contextJson);

      const completed = toolsAgent.stub.streamCalls.find((s) => s.eventType === "completed");
      expect(completed).toBeDefined();
      const data = JSON.parse(completed!.data);
      expect(data.tool_count).toBe(2);
    });
  });

  describe("bash tool", () => {
    it("echo command returns stdout", async () => {
      const input = JSON.stringify({ action: "echo" });
      const result = await bashAgent.agent.execute(input, contextJson);
      expect(result.tag).toBe("ok");

      const parsed = JSON.parse(result.val);
      expect(parsed.data.bash_result.stdout).toBe("echo hello");
      expect(parsed.data.bash_result.exit_code).toBe(0);
    });

    it("non-zero exit code throws (caught by bridge as err)", async () => {
      const input = JSON.stringify({ action: "exit-code" });
      const result = await bashAgent.agent.execute(input, contextJson);
      expect(result.tag).toBe("err");
      expect(result.val).toContain("exited with code 42");
    });

    it("stub records bash tool calls", async () => {
      const input = JSON.stringify({ action: "echo" });
      await bashAgent.agent.execute(input, contextJson);

      const bashCalls = bashAgent.stub.toolCalls.filter((c) => c.name === "bash");
      expect(bashCalls).toHaveLength(1);
      expect(bashCalls[0].args).toEqual({ command: "echo hello" });
    });
  });
});
