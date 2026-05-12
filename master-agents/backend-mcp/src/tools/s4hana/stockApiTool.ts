/**
 * S/4HANA Material Stock API MCP tool (OData V2).
 *
 * Translated from the Python FastMCP implementation in new-tools.txt.
 * Provides a universal OData V2 gateway for material stock queries.
 */
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';

import { registerToolWithLogging } from '../../utils/toolLogger.js';
import { getS4Config, s4hanaRequestV2 } from '../../utils/s4hanaClient.js';

const stockApiInputSchema = z.object({
  path: z
    .string()
    .default('')
    .describe(
      'Everything after the service root URL. ' +
      'Examples: "$metadata" (use accept="application/xml"), ' +
      '"A_MaterialStock?$top=5", ' +
      '"A_MaterialStock(\'TG11\')?$expand=to_MatlStkInAcctMod", ' +
      '"A_MatlStkInAcctMod?$filter=Material eq \'TG11\'&$top=20", ' +
      '"A_MatlStkInAcctMod?$filter=Plant eq \'1710\'&$select=Material,Plant,StorageLocation,MatlWrhsStkQtyInMatlBaseUnit,MaterialBaseUnit&$top=50"',
    ),
  accept: z
    .string()
    .default('application/json')
    .describe('HTTP Accept header. "application/json" (default) or "application/xml" for $metadata.'),
});

type StockApiInput = z.infer<typeof stockApiInputSchema>;

export function registerStockApiTool(server: McpServer): void {
  registerToolWithLogging(
    server,
    'stock_api',
    {
      title: 'Material Stock API Gateway',
      description:
        'Execute any request against the S/4HANA Material Stock API (OData V2). ' +
        'Thin HTTP gateway — you provide the URL path; authentication is handled automatically. ' +
        'NOTE: OData V2 service — collections are wrapped in {d:{results:[...]}}. ' +
        'This tool normalizes the response so you always get a flat "data" list. ' +
        'Fetch $metadata first if unsure about entities/fields.',
      inputSchema: stockApiInputSchema.shape,
    },
    async ({ path, accept }: StockApiInput) => {
      const cfg = getS4Config();
      if (!cfg.stockEndpoint) {
        return _errResult('S4MATERIAL_STOCK_ENDPOINT not configured in .env');
      }
      if (!cfg.user || !cfg.password) {
        return _errResult('S4HANA_USER or S4HANA_PASSWORD not configured in .env');
      }

      const base = cfg.stockEndpoint.replace(/\/$/, '');
      const url = path ? `${base}/${path}` : base;
      const result = await s4hanaRequestV2(url, accept);

      if (result.success) {
        return {
          content: [{ type: 'text' as const, text: JSON.stringify(result, null, 2) }],
          structuredContent: result,
        };
      }
      return _errResult(result.error ?? 'Unknown error');
    },
  );
}

function _errResult(error: string) {
  // NOTE: Do NOT set isError: true here. When isError is true, the MCP client
  // raises a ToolException which crashes the agent instead of letting it see the
  // error and retry with corrected parameters. By returning the error as normal
  // content, the LLM can read it, understand what went wrong, and try again.
  const result = { success: false, error, data: [], count: 0 };
  return {
    content: [{ type: 'text' as const, text: JSON.stringify(result, null, 2) }],
    structuredContent: result,
  };
}
