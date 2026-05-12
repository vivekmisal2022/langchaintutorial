/**
 * S/4HANA Product API MCP tools.
 *
 * Translated from the Python FastMCP implementation in new-tools.txt.
 * Provides product search, query, and a universal OData V4 gateway.
 */
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';

import { registerToolWithLogging } from '../../utils/toolLogger.js';
import { getS4Config, s4hanaRequest } from '../../utils/s4hanaClient.js';

// ---------------------------------------------------------------------------
// search_product_descriptions
// ---------------------------------------------------------------------------

const searchDescInputSchema = z.object({
  search_text: z
    .string()
    .describe("Text to search for in product descriptions. Examples: 'cat', 'food', 'battery', 'LED'"),
  language: z
    .string()
    .default('EN')
    .describe("Language code for the description. Default 'EN'. Common: EN, DE, JA, FR, ES, ZH, KO"),
  top: z
    .number()
    .int()
    .positive()
    .default(20)
    .describe('Maximum number of results (default: 20)'),
});

type SearchDescInput = z.infer<typeof searchDescInputSchema>;

export function registerSearchProductDescriptionsTool(server: McpServer): void {
  registerToolWithLogging(
    server,
    'search_product_descriptions',
    {
      title: 'Search Product Descriptions',
      description:
        'Search for products by their description text in a specific language. ' +
        "This is the BEST way to find products by name/text (e.g. 'cat food', 'battery'). " +
        'It searches the ProductDescription entity directly.',
      inputSchema: searchDescInputSchema.shape,
    },
    async ({ search_text, language, top }: SearchDescInput) => {
      const cfg = getS4Config();
      if (!cfg.productEndpoint) {
        return _errResult('S4PRODUCT_ENDPOINT not configured in .env');
      }
      if (!cfg.user || !cfg.password) {
        return _errResult('S4HANA_USER or S4HANA_PASSWORD not configured in .env');
      }

      const safeSearch = search_text.replace(/'/g, "''");
      const lang = language.toUpperCase();
      const filter = `contains(ProductDescription,'${safeSearch}') and Language eq '${lang}'`;

      const params = new URLSearchParams({
        $filter: filter,
        $select: 'Product,Language,ProductDescription',
        $top: String(top ?? 20),
        $count: 'true',
      });

      const url = `${cfg.productEndpoint.replace(/\/$/, '')}/ProductDescription?${params}`;
      const result = await s4hanaRequest(url);

      if (result.success) {
        const output = {
          ...result,
          search_info: { search_text, language: lang },
        };
        return _okResult(output);
      }
      return _errResult(result.error ?? 'Unknown error');
    },
  );
}

// ---------------------------------------------------------------------------
// query_products
// ---------------------------------------------------------------------------

const queryProductsInputSchema = z.object({
  filter_expression: z
    .string()
    .default('')
    .describe(
      "OData $filter on Product entity fields. Example: \"startswith(Product,'APJ')\" or \"ProductType eq 'FERT'\"",
    ),
  select_fields: z
    .string()
    .default('')
    .describe("Comma-separated fields. Example: 'Product,ProductType,BaseUnit'"),
  top: z
    .number()
    .int()
    .positive()
    .default(10)
    .describe('Max results (default: 10). Use 20-50 when searching by description.'),
  skip: z.number().int().default(0).describe('Skip N results for pagination (default: 0)'),
  orderby: z.string().default('').describe("Sort field. Example: 'Product asc' or 'CreationDate desc'"),
  expand: z
    .string()
    .default('')
    .describe(
      "IMPORTANT! Use '_ProductDescription' to get readable product names. Without this you only get technical IDs.",
    ),
});

type QueryProductsInput = z.infer<typeof queryProductsInputSchema>;

export function registerQueryProductsTool(server: McpServer): void {
  registerToolWithLogging(
    server,
    'query_products',
    {
      title: 'Query Products',
      description:
        'Query the S/4HANA Product Master API with flexible OData parameters. ' +
        "CRITICAL: The 'Product' field is just a technical ID (like 'APJ123'), NOT the readable name! " +
        "To get human-readable product names, you MUST use expand='_ProductDescription'.",
      inputSchema: queryProductsInputSchema.shape,
    },
    async ({ filter_expression, select_fields, top, skip, orderby, expand }: QueryProductsInput) => {
      const cfg = getS4Config();
      if (!cfg.productEndpoint) {
        return _errResult('S4PRODUCT_ENDPOINT not configured in .env');
      }
      if (!cfg.user || !cfg.password) {
        return _errResult('S4HANA_USER or S4HANA_PASSWORD not configured in .env');
      }

      const params = new URLSearchParams();
      if (filter_expression) params.set('$filter', filter_expression);
      if (select_fields) params.set('$select', select_fields);
      if (top) params.set('$top', String(top));
      if (skip) params.set('$skip', String(skip));
      if (orderby) params.set('$orderby', orderby);
      if (expand) params.set('$expand', expand);
      params.set('$count', 'true');

      const qs = params.toString();
      const url = `${cfg.productEndpoint.replace(/\/$/, '')}/Product${qs ? `?${qs}` : ''}`;
      const result = await s4hanaRequest(url);

      if (result.success) {
        const output = {
          ...result,
          query_used: {
            filter: filter_expression || '(none)',
            select: select_fields || '(all fields)',
            top,
            skip,
          },
        };
        return _okResult(output);
      }
      return _errResult(result.error ?? 'Unknown error');
    },
  );
}

// ---------------------------------------------------------------------------
// product_api — universal OData V4 gateway
// ---------------------------------------------------------------------------

const productApiInputSchema = z.object({
  path: z
    .string()
    .default('')
    .describe(
      'Everything after the service root URL. Examples: ' +
      '"Product?$top=5&$expand=_ProductDescription", ' +
      '"Product(\'TG-17\')", ' +
      '"ProductDescription?$filter=contains(ProductDescription,\'cat\') and Language eq \'EN\'&$top=20", ' +
      '"$metadata" (use accept="application/xml")',
    ),
  accept: z
    .string()
    .default('application/json')
    .describe('HTTP Accept header. Use "application/json" (default) or "application/xml" for $metadata.'),
});

type ProductApiInput = z.infer<typeof productApiInputSchema>;

export function registerProductApiTool(server: McpServer): void {
  registerToolWithLogging(
    server,
    'product_api',
    {
      title: 'Product API Gateway',
      description:
        'Execute any OData V4 request against the S/4HANA Product Master API. ' +
        'Thin universal HTTP gateway — you provide the URL path and query string. ' +
        'Call get_product_api_documentation first if unsure about entities/fields.',
      inputSchema: productApiInputSchema.shape,
    },
    async ({ path, accept }: ProductApiInput) => {
      const cfg = getS4Config();
      if (!cfg.productEndpoint) {
        return _errResult('S4PRODUCT_ENDPOINT not configured in .env');
      }
      if (!cfg.user || !cfg.password) {
        return _errResult('S4HANA_USER or S4HANA_PASSWORD not configured in .env');
      }

      const base = cfg.productEndpoint.replace(/\/$/, '');
      const url = path ? `${base}/${path}` : base;
      const result = await s4hanaRequest(url, accept);
      return result.success ? _okResult(result) : _errResult(result.error ?? 'Unknown error');
    },
  );
}

// ---------------------------------------------------------------------------
// get_product_api_documentation
// ---------------------------------------------------------------------------

export function registerGetProductApiDocsTool(server: McpServer): void {
  registerToolWithLogging(
    server,
    'get_product_api_documentation',
    {
      title: 'Product API Documentation',
      description:
        'Get documentation for the S/4HANA Product Master API. ' +
        'Call this FIRST to understand how to query products.',
      inputSchema: {},
    },
    async () => {
      const docs = PRODUCT_API_DOCUMENTATION;
      return {
        content: [{ type: 'text' as const, text: docs }],
      };
    },
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function _okResult(data: unknown) {
  return {
    content: [{ type: 'text' as const, text: JSON.stringify(data, null, 2) }],
    structuredContent: data,
  };
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

// ---------------------------------------------------------------------------
// Inline API Documentation
// ---------------------------------------------------------------------------

const PRODUCT_API_DOCUMENTATION = `
# S/4HANA Product Master API Documentation

## Overview
The Product Master API is an OData V4 service for reading product data from S/4HANA.
Base URL is configured via S4PRODUCT_ENDPOINT environment variable.

## Key Entities

### Product
Main entity for product master records.
- **Product** (string) — Technical product ID (e.g. "APJ123", "TG-17"). NOT the readable name!
- **ProductType** (string) — e.g. "FERT" (finished), "HAWA" (trading goods), "ROH" (raw material)
- **BaseUnit** (string) — Base unit of measure (e.g. "EA", "KG")
- **CreationDate** (date)
- **LastChangeDate** (date)

### ProductDescription (navigation: _ProductDescription)
Human-readable product names in multiple languages.
- **Product** (string) — Links to Product entity
- **Language** (string) — Language key: EN, DE, JA, FR, ES, ZH, KO, etc.
- **ProductDescription** (string) — The actual readable product name

### ProductPlant (navigation: _ProductPlant)
Plant-level data for products.
- **Product**, **Plant**, **PurchasingGroup**, **MRPType**, etc.

## Common Query Patterns

### Find products by name/description
Best approach — query ProductDescription directly:
\`\`\`
ProductDescription?$filter=contains(ProductDescription,'cat') and Language eq 'EN'&$top=20
\`\`\`

### Get products with readable names
\`\`\`
Product?$top=10&$expand=_ProductDescription
\`\`\`

### Filter by product type
\`\`\`
Product?$filter=ProductType eq 'FERT'&$top=10&$expand=_ProductDescription
\`\`\`

### Get a specific product
\`\`\`
Product('TG-17')?$expand=_ProductDescription
\`\`\`

### Get plant data for a product
\`\`\`
ProductPlant?$filter=Product eq 'TG-17'&$select=Product,Plant
\`\`\`

## OData V4 Query Options
- **$filter** — Filter results: eq, ne, gt, lt, ge, le, contains(), startswith(), endswith()
- **$select** — Choose specific fields: \`$select=Product,ProductType\`
- **$top** — Limit results: \`$top=20\`
- **$skip** — Pagination offset: \`$skip=20\`
- **$orderby** — Sort: \`$orderby=Product asc\`
- **$expand** — Include related entities: \`$expand=_ProductDescription\`
- **$count** — Include total count: \`$count=true\`

## Important Notes
1. The "Product" field is a **technical ID**, not a human-readable name
2. Always use \`$expand=_ProductDescription\` to get readable names
3. \`$filter\` on Product entity cannot filter by description text — use the ProductDescription entity directly
4. The backend may not support \`tolower()\` — rely on server collation for case handling
5. Escape single quotes in filter values by doubling them: \`'O''Brien'\`
`;
