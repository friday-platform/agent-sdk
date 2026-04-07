export declare const toolCalls: Array<{ name: string; args: unknown }>;
export declare const logCalls: Array<{ level: number; message: string }>;
export declare const streamCalls: Array<{ eventType: string; data: string }>;
export declare const llmCalls: Array<unknown>;
export declare const httpCalls: Array<unknown>;
export declare function reset(): void;
export declare function callTool(name: string, args: string): Promise<string>;
export declare function listTools(): Array<{
  name: string;
  description: string;
  inputSchema: string;
}>;
export declare function llmGenerate(request: string): Promise<string>;
export declare function httpFetch(request: string): Promise<string>;
export declare function log(level: number, message: string): void;
export declare function streamEmit(eventType: string, data: string): void;
