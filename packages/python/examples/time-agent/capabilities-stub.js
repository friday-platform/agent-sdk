/**
 * Async host function implementations for time-agent fixture.
 *
 * callTool returns deterministic mock data for get_current_time and
 * convert_time. Unknown tools throw ComponentError for error path testing.
 *
 * jco's result-catch-handler trampoline wraps:
 *   - returned values as { tag: "ok", val }
 *   - caught errors as { tag: "err", val: getErrorPayload(e) }
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
  const parsed = await Promise.resolve(JSON.parse(args));
  if (name === "get_current_time") {
    return JSON.stringify({
      timezone: parsed.timezone ?? "UTC",
      datetime: "2025-01-01T12:00:00+00:00",
      is_dst: false,
    });
  }
  if (name === "convert_time") {
    return JSON.stringify({
      source: {
        timezone: parsed.source_timezone ?? "UTC",
        datetime: "2025-01-01T12:00:00+00:00",
        is_dst: false,
      },
      target: {
        timezone: parsed.target_timezone ?? "America/New_York",
        datetime: "2025-01-01T07:00:00-05:00",
        is_dst: false,
      },
      time_difference: "-5.0h",
    });
  }
  throw new ComponentError("tool-not-found");
}

export function listTools() {
  return [
    {
      name: "get_current_time",
      description: "Get current time in a specific timezone",
      inputSchema:
        '{"type":"object","properties":{"timezone":{"type":"string"}},"required":["timezone"]}',
    },
    {
      name: "convert_time",
      description: "Convert time between timezones",
      inputSchema:
        '{"type":"object","properties":{"source_timezone":{"type":"string"},"time":{"type":"string"},"target_timezone":{"type":"string"}},"required":["source_timezone","time","target_timezone"]}',
    },
  ];
}

export function log(level, message) {
  logCalls.push({ level, message });
}

export function streamEmit(eventType, data) {
  streamCalls.push({ eventType, data });
}

// Required by WIT but unused by time-agent fixture
export function llmGenerate(_request) {
  throw new ComponentError("not-implemented");
}

export function httpFetch(_request) {
  throw new ComponentError("not-implemented");
}
