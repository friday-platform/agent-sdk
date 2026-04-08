/**
 * On-demand agent loading with cache invalidation.
 *
 * Tests use loadAgent() instead of static imports. If the compiled artifact
 * is stale or missing, it automatically triggers a rebuild.
 */

import { access, stat } from "node:fs/promises";
import { join } from "node:path";
import { compileAgent } from "./compile.ts";
import { getAgentDir, getAgentJsPath, getAgentSourcePath, resolveSdkPath } from "./paths.ts";

/** Key SDK files to check for changes */
const SDK_FILES = [
  "friday_agent_sdk/__init__.py",
  "friday_agent_sdk/_bridge.py",
  "friday_agent_sdk/_types.py",
  "friday_agent_sdk/_decorator.py",
  "friday_agent_sdk/_context.py",
  "friday_agent_sdk/_result.py",
  "friday_agent_sdk/_parse.py",
  "friday_agent_sdk/_registry.py",
  "friday_agent_sdk/_serialize.py",
];

/**
 * Check if any source file is newer than the compiled output.
 */
async function isStale(agentDir: string, jsPath: string): Promise<boolean> {
  // If output doesn't exist, it's stale
  try {
    await access(jsPath);
  } catch {
    return true;
  }

  const jsStat = await stat(jsPath);
  const jsMtime = jsStat.mtime;

  // Check agent source
  const sourcePath = getAgentSourcePath(agentDir);
  try {
    const sourceStat = await stat(sourcePath);
    if (sourceStat.mtime > jsMtime) return true;
  } catch {
    // Source missing? Still stale
    return true;
  }

  // Check SDK files
  const sdkPath = resolveSdkPath(agentDir);
  for (const sdkFile of SDK_FILES) {
    try {
      const sdkFilePath = join(sdkPath, sdkFile);
      const sdkStat = await stat(sdkFilePath);
      if (sdkStat.mtime > jsMtime) return true;
    } catch {
      // File doesn't exist, skip
    }
  }

  return false;
}

/** Agent module interface */
export interface AgentModule {
  agent: {
    getMetadata(): string;
    execute(prompt: string, context: string): { tag: "ok" | "err"; val: string };
  };
}

/** Capabilities stub interface for test assertions */
export interface CapabilitiesStub {
  toolCalls: Array<{ name: string; args: unknown }>;
  logCalls: Array<{ level: number; message: string }>;
  streamCalls: Array<{ eventType: string; data: string }>;
  llmCalls: unknown[];
  httpCalls: unknown[];
  reset(): void;
}

/** Loaded agent with access to its stub for assertions */
export interface LoadedAgent {
  agent: AgentModule["agent"];
  stub: CapabilitiesStub;
}

/**
 * Load an agent, compiling on-demand if necessary.
 *
 * @param name - The agent name (e.g., "echo-agent")
 * @param opts - Options
 * @returns The compiled agent module with its stub
 *
 * @example
 * const { agent: echoAgent, stub } = await loadAgent("echo-agent");
 * // ... run agent ...
 * expect(stub.toolCalls).toHaveLength(1);
 */
export async function loadAgent(name: string, opts?: { force?: boolean }): Promise<LoadedAgent> {
  const agentDir = getAgentDir(name);
  const jsPath = getAgentJsPath(agentDir);
  const stubPath = join(agentDir, "agent-js", "capabilities.js");

  const stale = opts?.force || (await isStale(agentDir, jsPath));

  if (stale) {
    await compileAgent(name);
  }

  // Import both the agent module and its stub
  const [module, stub] = await Promise.all([import(jsPath), import(stubPath)]);

  return {
    agent: (module as AgentModule).agent,
    stub: stub as CapabilitiesStub,
  };
}

/**
 * Load multiple agents at once for batch testing.
 *
 * @param names - Array of agent names
 * @returns Map of name -> module
 */
export async function loadAgents(names: string[]): Promise<Record<string, AgentModule>> {
  const results: Record<string, AgentModule> = {};

  for (const name of names) {
    results[name] = await loadAgent(name);
  }

  return results;
}
