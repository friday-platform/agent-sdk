/**
 * Path resolution helpers for agent compilation.
 */

import { accessSync } from "node:fs";
import { dirname, join, resolve } from "node:path";

/**
 * Resolve the SDK path by walking up from the given directory.
 * Looks for packages/python with the friday_agent_sdk package.
 */
export function resolveSdkPath(fromDir: string): string {
  let dir = resolve(fromDir);
  for (let i = 0; i < 10; i++) {
    const parent = resolve(dir, "..");
    if (parent === dir) break;
    dir = parent;

    const candidates = [join(dir, "packages", "python"), join(dir, "sdk-python")];

    for (const candidate of candidates) {
      try {
        accessSync(join(candidate, "friday_agent_sdk", "__init__.py"));
        return candidate;
      } catch {
        /* not found, continue */
      }
    }
  }
  throw new Error(`Could not resolve SDK path from: ${fromDir}`);
}

/**
 * Resolve the WIT directory from the SDK path.
 */
export function resolveWitPath(sdkPath: string): string {
  // WIT is in packages/wit at the repo root, not inside sdk
  let dir = resolve(sdkPath);
  for (let i = 0; i < 10; i++) {
    const parent = resolve(dir, "..");
    if (parent === dir) break;
    dir = parent;

    const witDir = join(dir, "packages", "wit");
    try {
      accessSync(join(witDir, "agent.wit"));
      return witDir;
    } catch {
      /* not found, continue */
    }
  }
  throw new Error(`Could not resolve WIT path from SDK: ${sdkPath}`);
}

/**
 * Get the path to an example agent directory by name.
 */
export function getAgentDir(agentName: string): string {
  // From conformance tests, resolve to python examples
  const conformanceDir = dirname(new URL(import.meta.url).pathname);
  const agentDir = resolve(conformanceDir, "..", "..", "python", "examples", agentName);

  try {
    accessSync(join(agentDir, "agent.py"));
    return agentDir;
  } catch {
    throw new Error(`Agent "${agentName}" not found at ${agentDir}`);
  }
}

/**
 * Get the path to the built agent-js module.
 */
export function getAgentJsPath(agentDir: string): string {
  return join(agentDir, "agent-js", "agent.js");
}

/**
 * Get the path to agent.py source.
 */
export function getAgentSourcePath(agentDir: string): string {
  return join(agentDir, "agent.py");
}

/**
 * Get the path to the WASM artifact.
 */
export function getWasmPath(agentDir: string): string {
  return join(agentDir, "agent.wasm");
}

/**
 * Get the path to the agent-js output directory.
 */
export function getAgentJsDir(agentDir: string): string {
  return join(agentDir, "agent-js");
}

/**
 * Get the path to the preview2-shim within node_modules.
 * It may be in an example's node_modules (from previous builds) or at root.
 */
export function getPreview2ShimSource(): string {
  const conformanceDir = dirname(new URL(import.meta.url).pathname);

  // Try several locations where it might exist
  const candidates = [
    // In an example's node_modules (from vendored builds)
    resolve(
      conformanceDir,
      "..",
      "..",
      "python",
      "examples",
      "echo-agent",
      "node_modules",
      "@bytecodealliance",
      "preview2-shim",
    ),
    // At the root node_modules
    resolve(conformanceDir, "..", "..", "..", "node_modules", "@bytecodealliance", "preview2-shim"),
  ];

  for (const shimPath of candidates) {
    try {
      accessSync(join(shimPath, "package.json"));
      return shimPath;
    } catch {
      /* not found, try next */
    }
  }

  throw new Error(`preview2-shim not found. Run 'pnpm install' in the agent-sdk root first.`);
}
