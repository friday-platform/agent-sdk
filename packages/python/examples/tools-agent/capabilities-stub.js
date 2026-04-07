/**
 * Async host function implementations for tools-agent fixture.
 *
 * callTool is async (returns Promise) to prove JSPI suspension works.
 * log and streamEmit capture calls for test assertions.
 *
 * jco's result-catch-handler trampoline wraps:
 *   - returned values as { tag: "ok", val }
 *   - caught errors as { tag: "err", val: getErrorPayload(e) }
 * getErrorPayload extracts e.payload if present, so we throw
 * ComponentError-shaped objects for typed error propagation.
 */

/** @type {Array<{level: number, message: string}>} */
export const logCalls = [];

/** @type {Array<{eventType: string, data: string}>} */
export const streamCalls = [];

export function reset() {
  logCalls.length = 0;
  streamCalls.length = 0;
}

class ComponentError extends Error {
  constructor(payload) {
    super(typeof payload === "string" ? payload : `${String(payload)} (see error.payload)`);
    Object.defineProperty(this, "payload", {
      value: payload,
      enumerable: typeof payload !== "string",
    });
  }
}

export async function callTool(name, args) {
  // await proves JSPI suspension works (host returns a Promise)
  const parsed = await Promise.resolve(JSON.parse(args));
  if (name === "fail") {
    throw new ComponentError("tool-not-found");
  }
  return JSON.stringify({ tool: name, received: parsed });
}

export function listTools() {
  return [{ name: "echo", description: "Echoes input", inputSchema: '{"type":"object"}' }];
}

export function log(level, message) {
  logCalls.push({ level, message });
}

export function streamEmit(eventType, data) {
  streamCalls.push({ eventType, data });
}

// Required by WIT but unused by tools-agent fixture
export function llmGenerate(_request) {
  throw new ComponentError("not-implemented");
}

export function httpFetch(_request) {
  throw new ComponentError("not-implemented");
}
