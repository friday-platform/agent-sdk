/** @module Interface friday:agent/capabilities@0.1.0 **/
export function callTool(name: string, args: string): string;
export function listTools(): Array<ToolDefinition>;
export function log(level: number, message: string): void;
export function streamEmit(eventType: string, data: string): void;
export function llmGenerate(request: string): string;
export function httpFetch(request: string): string;
export type ToolDefinition = import('./friday-agent-types.js').ToolDefinition;
