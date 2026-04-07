/**
 * Unified deterministic capabilities stub for conformance tests.
 *
 * Provides all 6 WIT host function imports with predictable behavior
 * and call tracking for test assertions. Async functions return Promises
 * to validate JSPI suspension through jco's trampoline.
 *
 * jco's result-catch-handler trampoline wraps:
 *   - returned values as { tag: "ok", val }
 *   - caught errors as { tag: "err", val: getErrorPayload(e) }
 * getErrorPayload extracts e.payload if present, so we throw
 * ComponentError-shaped objects for typed error propagation.
 */

// ---------------------------------------------------------------------------
// Call tracking
// ---------------------------------------------------------------------------

/** @type {Array<{name: string, args: unknown}>} */
export const toolCalls = [];

/** @type {Array<{level: number, message: string}>} */
export const logCalls = [];

/** @type {Array<{eventType: string, data: string}>} */
export const streamCalls = [];

/** @type {Array<unknown>} */
export const llmCalls = [];

/** @type {Array<unknown>} */
export const httpCalls = [];

export function reset() {
  toolCalls.length = 0;
  logCalls.length = 0;
  streamCalls.length = 0;
  llmCalls.length = 0;
  httpCalls.length = 0;
}

// ---------------------------------------------------------------------------
// Error type matching jco's ComponentError convention
// ---------------------------------------------------------------------------

class ComponentError extends Error {
  constructor(payload) {
    super(typeof payload === "string" ? payload : `${String(payload)} (see error.payload)`);
    Object.defineProperty(this, "payload", {
      value: payload,
      enumerable: typeof payload !== "string",
    });
  }
}

// ---------------------------------------------------------------------------
// callTool — deterministic tool dispatch
// ---------------------------------------------------------------------------

export async function callTool(name, args) {
  const parsed = await Promise.resolve(JSON.parse(args));
  toolCalls.push({ name, args: parsed });

  if (name === "fail") {
    throw new ComponentError("tool-not-found");
  }

  if (name === "echo") {
    return JSON.stringify({ tool: "echo", received: parsed });
  }

  if (name === "bash") {
    const command = parsed.command ?? "";
    if (command.startsWith("exit ")) {
      const code = parseInt(command.split(" ")[1], 10);
      if (code !== 0) {
        throw new ComponentError(`command exited with code ${code}`);
      }
      return JSON.stringify({ stdout: "", stderr: "", exit_code: 0 });
    }
    return JSON.stringify({ stdout: command, stderr: "", exit_code: 0 });
  }

  // Generic passthrough for any other tool
  return JSON.stringify({ tool: name, received: parsed });
}

// ---------------------------------------------------------------------------
// listTools — fixed tool definitions
// ---------------------------------------------------------------------------

export function listTools() {
  return [
    { name: "echo", description: "Echoes input", inputSchema: '{"type":"object"}' },
    {
      name: "bash",
      description: "Execute a shell command",
      inputSchema:
        '{"type":"object","properties":{"command":{"type":"string"}},"required":["command"]}',
    },
  ];
}

// ---------------------------------------------------------------------------
// llmGenerate — deterministic mock LLM
// ---------------------------------------------------------------------------

export async function llmGenerate(request) {
  const parsed = await Promise.resolve(JSON.parse(request));
  llmCalls.push(parsed);

  if (parsed.model === "fail-model") {
    throw new ComponentError("llm-unavailable");
  }

  const response = {
    text: "mock response",
    object: null,
    model: parsed.model || "default-model",
    usage: { prompt_tokens: 10, completion_tokens: 5 },
    finish_reason: "stop",
  };

  if (parsed.output_schema) {
    response.text = null;
    response.object = { mock: true };
  }

  return JSON.stringify(response);
}

// ---------------------------------------------------------------------------
// httpFetch — deterministic mock HTTP
// ---------------------------------------------------------------------------

export async function httpFetch(request) {
  const parsed = await Promise.resolve(JSON.parse(request));
  httpCalls.push(parsed);

  if (parsed.url.includes("fail.example.com")) {
    throw new ComponentError("connection-refused");
  }

  return JSON.stringify({
    status: 200,
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ ok: true, url: parsed.url }),
  });
}

// ---------------------------------------------------------------------------
// log / streamEmit — capture for assertions
// ---------------------------------------------------------------------------

export function log(level, message) {
  logCalls.push({ level, message });
}

export function streamEmit(eventType, data) {
  streamCalls.push({ eventType, data });
}
