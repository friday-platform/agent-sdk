/**
 * Faithful replication of the atlas build pipeline for a single agent.
 *
 * Compiles Python source to WASM via componentize-py, transpiles to JS via jco,
 * vendors preview2-shim, and rewrites imports for conformance testing.
 */

import { execFile } from "node:child_process";
import { access, copyFile, mkdir, readdir, readFile, writeFile, rm } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { promisify } from "node:util";
import {
  getAgentDir,
  getAgentJsDir,
  getAgentSourcePath,
  getPreview2ShimSource,
  getWasmPath,
  resolveSdkPath,
  resolveWitPath,
} from "./paths.ts";

const execFileAsync = promisify(execFile);

/**
 * Capabilities stub content for conformance testing - full implementation.
 * This is the transpiled version of stubs/capabilities-stub.ts.
 */
const CAPABILITIES_STUB = `
// Call tracking
export const toolCalls = [];
export const logCalls = [];
export const streamCalls = [];
export const llmCalls = [];
export const httpCalls = [];

export function reset() {
  toolCalls.length = 0;
  logCalls.length = 0;
  streamCalls.length = 0;
  llmCalls.length = 0;
  httpCalls.length = 0;
}

// ComponentError for jco error propagation
class ComponentError extends Error {
  constructor(payload) {
    super(typeof payload === "string" ? payload : \`\${String(payload)} (see error.payload)\`);
    this.payload = payload;
    Object.defineProperty(this, "payload", {
      value: payload,
      enumerable: typeof payload !== "string",
    });
  }
}

// callTool — deterministic tool dispatch
export async function callTool(name, args) {
  const parsed = await Promise.resolve(JSON.parse(args));
  toolCalls.push({ name, args: parsed });

  if (name === "fail" || name === "nonexistent_tool") {
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
        throw new ComponentError(\`command exited with code \${code}\`);
      }
      return JSON.stringify({ stdout: "", stderr: "", exit_code: 0 });
    }
    return JSON.stringify({ stdout: command, stderr: "", exit_code: 0 });
  }

  return JSON.stringify({ tool: name, received: parsed });
}

// listTools — fixed tool definitions
export function listTools() {
  return [
    { name: "echo", description: "Echoes input", inputSchema: '{"type":"object"}' },
    {
      name: "bash",
      description: "Execute a shell command",
      inputSchema: '{"type":"object","properties":{"command":{"type":"string"}},"required":["command"]}',
    },
  ];
}

// llmGenerate — deterministic mock LLM
export async function llmGenerate(request) {
  const parsed = JSON.parse(request);
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

// httpFetch — deterministic mock HTTP
export async function httpFetch(request) {
  const parsed = JSON.parse(request);
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

// log / streamEmit — capture for assertions
export function log(level, message) {
  logCalls.push({ level, message });
}

export function streamEmit(eventType, data) {
  streamCalls.push({ eventType, data });
}
`;

/** Error type for build failures with phase information */
export class AgentBuildError extends Error {
  constructor(
    message: string,
    readonly phase: "prereqs" | "compile" | "transpile" | "write",
  ) {
    super(message);
    this.name = "AgentBuildError";
  }
}

/** Check that a CLI tool exists and return its version */
async function checkPrerequisite(
  tool: string,
  versionFlag: string,
  installHint: string,
): Promise<string> {
  try {
    const { stdout } = await execFileAsync(tool, [versionFlag]);
    return stdout.trim();
  } catch {
    throw new AgentBuildError(
      `"${tool}" not found on PATH.\n\nInstall it:\n  ${installHint}`,
      "prereqs",
    );
  }
}

/** Verify all prerequisites are installed */
async function checkPrerequisites(): Promise<{
  componentizePyVersion: string;
  jcoVersion: string;
}> {
  const [componentizePyVersion, jcoVersion] = await Promise.all([
    checkPrerequisite("componentize-py", "--version", "pip install componentize-py"),
    checkPrerequisite("jco", "--version", "npm install -g @bytecodealliance/jco"),
  ]);
  return { componentizePyVersion, jcoVersion };
}

/** Run componentize-py to compile Python to WASM */
async function runComponentizePy(
  agentDir: string,
  sdkPath: string,
  witPath: string,
  entryPoint: string,
): Promise<void> {
  const wasmOutput = getWasmPath(agentDir);

  try {
    await execFileAsync("componentize-py", [
      "-d",
      witPath,
      "-w",
      "friday:agent/friday-agent",
      "componentize",
      entryPoint,
      "-p",
      agentDir,
      "-p",
      sdkPath,
      "-o",
      wasmOutput,
    ]);
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : String(error);
    throw new AgentBuildError(`componentize-py failed:\n${msg}`, "compile");
  }
}

/** Run jco transpile to convert WASM to JS */
async function runJcoTranspile(agentDir: string): Promise<void> {
  const wasmOutput = getWasmPath(agentDir);
  const jsOutputDir = getAgentJsDir(agentDir);

  try {
    await execFileAsync("jco", [
      "transpile",
      wasmOutput,
      "-o",
      jsOutputDir,
      "--async-mode",
      "jspi",
      "--async-imports",
      "friday:agent/capabilities#call-tool",
      "--async-imports",
      "friday:agent/capabilities#llm-generate",
      "--async-imports",
      "friday:agent/capabilities#http-fetch",
      "--async-exports",
      "friday:agent/agent#execute",
      "--map",
      "friday:agent/capabilities=./capabilities.js",
    ]);
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : String(error);
    throw new AgentBuildError(`jco transpile failed:\n${msg}`, "transpile");
  }
}

/** Write the capabilities stub for test-time injection */
async function writeCapabilitiesStub(jsOutputDir: string): Promise<void> {
  await writeFile(join(jsOutputDir, "capabilities.js"), CAPABILITIES_STUB);
}

/** Recursively copy a directory */
async function copyDir(src: string, dest: string): Promise<void> {
  await mkdir(dest, { recursive: true });
  const entries = await readdir(src, { withFileTypes: true });
  for (const entry of entries) {
    const srcPath = join(src, entry.name);
    const destPath = join(dest, entry.name);
    if (entry.isDirectory()) {
      await copyDir(srcPath, destPath);
    } else {
      await copyFile(srcPath, destPath);
    }
  }
}

/** Vendor preview2-shim into the agent output directory */
async function vendorPreview2Shim(srcShimDir: string, destDir: string): Promise<void> {
  await copyDir(srcShimDir, destDir);
}

/** Rewrite bare @bytecodealliance/preview2-shim imports to relative paths */
async function rewriteShimImports(agentJsPath: string): Promise<void> {
  const content = await readFile(agentJsPath, "utf-8");
  const rewritten = content.replace(
    /from\s+['"]@bytecodealliance\/preview2-shim\/([^'"]+)['"]/g,
    (_match, subpath) =>
      `from '../node_modules/@bytecodealliance/preview2-shim/lib/nodejs/${subpath}.js'`,
  );
  await writeFile(agentJsPath, rewritten);
}

/** Build a single agent from source */
export async function compileAgent(
  agentName: string,
  opts?: { entryPoint?: string },
): Promise<void> {
  const agentDir = getAgentDir(agentName);
  const entryPoint = opts?.entryPoint ?? "agent";

  // Verify source exists
  const sourcePath = getAgentSourcePath(agentDir);
  try {
    await access(sourcePath);
  } catch {
    throw new AgentBuildError(`Entry point "${entryPoint}.py" not found in ${agentDir}`, "prereqs");
  }

  // Resolve SDK and WIT paths
  const sdkPath = resolveSdkPath(agentDir);
  const witPath = resolveWitPath(sdkPath);

  // Check prerequisites
  await checkPrerequisites();

  // Clean up any previous build
  const jsOutputDir = getAgentJsDir(agentDir);
  const wasmOutput = getWasmPath(agentDir);
  await rm(jsOutputDir, { recursive: true, force: true });
  await rm(wasmOutput, { force: true });

  // 1. Run componentize-py
  await runComponentizePy(agentDir, sdkPath, witPath, entryPoint);

  // 2. Run jco transpile
  await runJcoTranspile(agentDir);

  // 3. Write capabilities stub
  await writeCapabilitiesStub(jsOutputDir);

  // 4. Vendor preview2-shim
  const shimSource = getPreview2ShimSource();
  const shimDestDir = join(jsOutputDir, "node_modules", "@bytecodealliance", "preview2-shim");
  await vendorPreview2Shim(shimSource, shimDestDir);

  // 5. Rewrite imports
  const agentJsPath = join(jsOutputDir, "agent.js");
  await rewriteShimImports(agentJsPath);
}

/** Clean up build artifacts for an agent */
export async function cleanAgent(agentName: string): Promise<void> {
  const agentDir = getAgentDir(agentName);
  const jsOutputDir = getAgentJsDir(agentDir);
  const wasmOutput = getWasmPath(agentDir);

  await rm(jsOutputDir, { recursive: true, force: true });
  await rm(wasmOutput, { force: true });
}
