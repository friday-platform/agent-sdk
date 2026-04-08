/**
 * Conformance test build system - public API.
 *
 * Provides on-demand compilation and loading for WASM agent conformance tests.
 */

export { compileAgent, cleanAgent, AgentBuildError } from "./compile.ts";
export { loadAgent, loadAgents, type AgentModule } from "./loader.ts";
export { getAgentDir, getAgentJsPath, resolveSdkPath, resolveWitPath } from "./paths.ts";
