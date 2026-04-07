/** @module Interface friday:agent/agent@0.1.0 **/
export function getMetadata(): string;
export function execute(prompt: string, context: string): AgentResult;
export type AgentResult = import('./friday-agent-types.js').AgentResult;
