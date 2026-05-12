import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import type { ZodRawShape } from 'zod';

import { logError, logToolExecution } from './logger.js';

/**
 * Registers a tool with automatic logging of input/output.
 * Wraps the original callback to log execution details.
 */
export function registerToolWithLogging<InputArgs extends ZodRawShape, OutputArgs extends ZodRawShape>(
  server: McpServer,
  toolName: string,
  config: {
    title?: string;
    description?: string;
    inputSchema?: InputArgs;
    outputSchema?: OutputArgs;
    annotations?: {
      [x: string]: unknown;
      title?: string;
      readOnlyHint?: boolean;
      destructiveHint?: boolean;
      idempotentHint?: boolean;
      openWorldHint?: boolean;
    };
    _meta?: Record<string, unknown>;
  },
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  callback: (args: any, extra?: any) => any,
): void {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const wrappedCallback = async (args: any, extra?: any) => {
    try {
      const result = await callback(args, extra);
      logToolExecution(toolName, args, result);
      return result;
    } catch (error) {
      logError(`Tool execution failed: ${toolName}`, error);
      throw error;
    }
  };

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  server.registerTool(toolName, config, wrappedCallback as any);
}
