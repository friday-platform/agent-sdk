/**
 * Async host function implementations for llm-http-agent fixture.
 *
 * llmGenerate and httpFetch are async (return Promise) to prove JSPI
 * suspension works. Error paths use ComponentError for typed propagation
 * through jco's result-catch-handler trampoline.
 */

/** @type {Array<{level: number, message: string}>} */
export const logCalls = [];

export function reset() {
  logCalls.length = 0;
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

export async function llmGenerate(request) {
  const parsed = await Promise.resolve(JSON.parse(request));
  if (parsed.model === "fail-model") {
    throw new ComponentError("llm-unavailable");
  }
  return JSON.stringify({
    text: "mock response",
    object: null,
    model: parsed.model || "default-model",
    usage: { prompt_tokens: 10, completion_tokens: 5 },
    finish_reason: "stop",
  });
}

export async function httpFetch(request) {
  const parsed = await Promise.resolve(JSON.parse(request));
  if (parsed.url.includes("fail.example.com")) {
    throw new ComponentError("connection-refused");
  }
  return JSON.stringify({
    status: 200,
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ ok: true, url: parsed.url }),
  });
}

// Required by jco-generated agent.js — these stubs are unused by this fixture
// but must be present since the WIT interface exports them all.
export async function callTool(name, args) {
  const parsed = await Promise.resolve(JSON.parse(args));
  if (name === "fail") {
    throw new ComponentError("tool-not-found");
  }
  return JSON.stringify({ tool: name, received: parsed });
}

export function listTools() {
  return [];
}

export function log(level, message) {
  logCalls.push({ level, message });
}

export function streamEmit(_eventType, _data) {}
