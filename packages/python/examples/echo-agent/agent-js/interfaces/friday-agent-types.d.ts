/** @module Interface friday:agent/types@0.1.0 **/
export interface ToolDefinition {
  name: string,
  description: string,
  inputSchema: string,
}
export type AgentResult = AgentResultOk | AgentResultErr;
export interface AgentResultOk {
  tag: 'ok',
  val: string,
}
export interface AgentResultErr {
  tag: 'err',
  val: string,
}
