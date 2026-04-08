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

/** Tracked tool call with parsed arguments */
export interface ToolCall {
  name: string;
  args: unknown;
}

/** Tracked log call */
export interface LogCall {
  level: number;
  message: string;
}

/** Tracked stream emit call */
export interface StreamCall {
  eventType: string;
  data: string;
}

/** @type {ToolCall[]} */
export const toolCalls: ToolCall[] = [];

/** @type {LogCall[]} */
export const logCalls: LogCall[] = [];

/** @type {StreamCall[]} */
export const streamCalls: StreamCall[] = [];

/** @type {unknown[]} */
export const llmCalls: unknown[] = [];

/** @type {unknown[]} */
export const httpCalls: unknown[] = [];

/** Reset all call tracking arrays */
export function reset(): void {
  toolCalls.length = 0;
  logCalls.length = 0;
  streamCalls.length = 0;
  llmCalls.length = 0;
  httpCalls.length = 0;
}

// ---------------------------------------------------------------------------
// Error type matching jco's ComponentError convention
// ---------------------------------------------------------------------------

/** Error payload type for jco's ComponentError convention */
export type ErrorPayload = string | { [key: string]: unknown };

/** Component error matching jco's convention */
class ComponentError extends Error {
  readonly payload: ErrorPayload;

  constructor(payload: ErrorPayload) {
    super(typeof payload === "string" ? payload : `${String(payload)} (see error.payload)`);
    this.payload = payload;
    Object.defineProperty(this, "payload", {
      value: payload,
      enumerable: typeof payload !== "string",
    });
  }
}

// ---------------------------------------------------------------------------
// Tool definition type
// ---------------------------------------------------------------------------

/** WIT tool definition */
export interface ToolDefinition {
  name: string;
  description: string;
  inputSchema: string;
}

// ---------------------------------------------------------------------------
// callTool — deterministic tool dispatch
// ---------------------------------------------------------------------------

/** Bash tool result */
interface BashResult {
  stdout: string;
  stderr: string;
  exit_code: number;
}

/** Generic tool result */
interface ToolResult {
  tool: string;
  received: unknown;
}

/**
 * Call a tool by name with JSON-serialized arguments.
 * @param name - Tool name
 * @param args - JSON-serialized arguments
 * @returns JSON-serialized result
 */
export async function callTool(name: string, args: string): Promise<string> {
  const parsed = await Promise.resolve(JSON.parse(args));
  toolCalls.push({ name, args: parsed });

  if (name === "fail" || name === "nonexistent_tool") {
    throw new ComponentError("tool-not-found");
  }

  if (name === "echo") {
    const result: ToolResult = { tool: "echo", received: parsed };
    return JSON.stringify(result);
  }

  if (name === "bash") {
    const command = (parsed as { command?: string }).command ?? "";
    if (command.startsWith("exit ")) {
      const code = parseInt(command.split(" ")[1], 10);
      if (code !== 0) {
        throw new ComponentError(`command exited with code ${code}`);
      }
      const result: BashResult = { stdout: "", stderr: "", exit_code: 0 };
      return JSON.stringify(result);
    }
    const result: BashResult = { stdout: command, stderr: "", exit_code: 0 };
    return JSON.stringify(result);
  }

  // Generic passthrough for any other tool
  const result: ToolResult = { tool: name, received: parsed };
  return JSON.stringify(result);
}

// ---------------------------------------------------------------------------
// listTools — fixed tool definitions
// ---------------------------------------------------------------------------

/**
 * List available tools with their schemas.
 * @returns Array of tool definitions
 */
export function listTools(): ToolDefinition[] {
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
// LLM types
// ---------------------------------------------------------------------------

/** LLM message */
export interface LlmMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

/** LLM request */
export interface LlmRequest {
  model?: string;
  messages: LlmMessage[];
  output_schema?: Record<string, unknown>;
  provider_options?: Record<string, unknown>;
}

/** Token usage stats */
export interface LlmUsage {
  prompt_tokens: number;
  completion_tokens: number;
}

/** LLM response */
export interface LlmResponse {
  text: string | null;
  object: unknown | null;
  model: string;
  usage: LlmUsage;
  finish_reason: string;
}

// ---------------------------------------------------------------------------
// llmGenerate — deterministic mock LLM
// ---------------------------------------------------------------------------

/**
 * Generate an LLM response deterministically.
 * @param request - JSON-serialized request
 * @returns JSON-serialized response
 */
export async function llmGenerate(request: string): Promise<string> {
  const parsed = JSON.parse(request) as LlmRequest;
  llmCalls.push(parsed);

  if (parsed.model === "fail-model") {
    throw new ComponentError("llm-unavailable");
  }

  const response: LlmResponse = {
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
// HTTP types
// ---------------------------------------------------------------------------

/** HTTP request */
export interface HttpRequest {
  url: string;
  method?: string;
  headers?: Record<string, string>;
  body?: string;
  timeout_ms?: number;
}

/** HTTP response */
export interface HttpResponse {
  status: number;
  headers: Record<string, string>;
  body: string;
}

// ---------------------------------------------------------------------------
// httpFetch — deterministic mock HTTP
// ---------------------------------------------------------------------------

/**
 * Fetch a URL deterministically.
 * @param request - JSON-serialized request
 * @returns JSON-serialized response
 */
export async function httpFetch(request: string): Promise<string> {
  const parsed = JSON.parse(request) as HttpRequest;
  httpCalls.push(parsed);

  if (parsed.url.includes("fail.example.com")) {
    throw new ComponentError("connection-refused");
  }

  const response: HttpResponse = {
    status: 200,
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ ok: true, url: parsed.url }),
  };

  return JSON.stringify(response);
}

// ---------------------------------------------------------------------------
// log / streamEmit — capture for assertions
// ---------------------------------------------------------------------------

/**
 * Log a message.
 * @param level - Log level (0=trace, 1=info, etc.)
 * @param message - Log message
 */
export function log(level: number, message: string): void {
  logCalls.push({ level, message });
}

/**
 * Emit a stream event.
 * @param eventType - Event type name
 * @param data - JSON-serialized event data
 */
export function streamEmit(eventType: string, data: string): void {
  streamCalls.push({ eventType, data });
}
