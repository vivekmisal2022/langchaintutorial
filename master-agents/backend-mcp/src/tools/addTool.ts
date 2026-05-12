import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';

import { registerToolWithLogging } from '../utils/toolLogger.js';

const additionSchema = z.object({
  a: z.number(),
  b: z.number(),
});

const additionSchemaShape = additionSchema.shape;

const additionResultSchema = z.object({
  result: z.number(),
});

const additionResultSchemaShape = additionResultSchema.shape;

type AdditionInput = z.infer<typeof additionSchema>;
type AdditionOutput = z.infer<typeof additionResultSchema>;

export function registerAddTool(server: McpServer): void {
  registerToolWithLogging(
    server,
    'add',
    {
      title: 'Addition Tool',
      description: 'Add two numbers',
      inputSchema: additionSchemaShape,
      outputSchema: additionResultSchemaShape,
    },
    async ({ a, b }: AdditionInput) => {
      const output: AdditionOutput = { result: a + b };

      return {
        content: [{ type: 'text', text: JSON.stringify(output) }],
        structuredContent: output,
      };
    },
  );
}
