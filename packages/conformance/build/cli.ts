/**
 * CLI for pre-building all conformance test agents.
 *
 * Usage: node --experimental-wasm-jspi --import tsx build/cli.ts
 * Or: pnpm build:agents
 */

import { readdir } from "node:fs/promises";
import { join, resolve } from "node:path";
import { compileAgent } from "./compile.ts";

const EXAMPLES_DIR = resolve(import.meta.dirname, "..", "..", "python", "examples");

async function getAgentNames(): Promise<string[]> {
  const entries = await readdir(EXAMPLES_DIR, { withFileTypes: true });
  const names: string[] = [];

  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    // Check if it has an agent.py
    try {
      const agentPath = join(EXAMPLES_DIR, entry.name, "agent.py");
      await import("node:fs/promises").then((fs) => fs.access(agentPath));
      names.push(entry.name);
    } catch {
      // No agent.py, skip
    }
  }

  return names.sort();
}

async function main() {
  const names = await getAgentNames();
  console.log(`Found ${names.length} agents to build:`);
  console.log(names.map((n) => `  - ${n}`).join("\n"));
  console.log();

  let success = 0;
  let failed = 0;

  for (const name of names) {
    process.stdout.write(`Building ${name}... `);
    try {
      await compileAgent(name);
      console.log("✓");
      success++;
    } catch (error: unknown) {
      console.log("✗");
      const msg = error instanceof Error ? error.message : String(error);
      console.error(`  Error: ${msg}`);
      failed++;
    }
  }

  console.log();
  console.log(`Build complete: ${success} succeeded, ${failed} failed`);

  if (failed > 0) {
    process.exit(1);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
