import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import express, { type Request, type Response } from 'express';
import cors from 'cors';
import * as dotenv from 'dotenv';

// Load environment variables from .env.local (or .env)
dotenv.config({ path: '.env.local' });
dotenv.config(); // Fallback to .env if .env.local doesn't exist

import { registerAddTool } from './tools/addTool.js';
import { registerWebSearchTool, registerWebResearchTool } from './tools/webSearchTool.js';
import { registerDocumentSearchTool } from './tools/documentTools.js';
import { registerTimeAndPlaceTool } from './tools/timeAndPlaceTool.js';
import {
  registerSearchProductDescriptionsTool,
  registerQueryProductsTool,
  registerProductApiTool,
  registerGetProductApiDocsTool,
} from './tools/s4hana/productTools.js';
import { registerStockApiTool } from './tools/s4hana/stockApiTool.js';
import {
  registerMemoryLoadTool,
  registerMemorySaveTool,
  registerMemoryDeleteTool,
} from './tools/memoryTools.js';
import documentRoutes from './api/documentRoutes.js';

// Log configuration status
console.log('🔧 Configuration:');
console.log(`   LOG_LEVEL: ${process.env.LOG_LEVEL || 'info'}`);
console.log(`   PORT: ${process.env.PORT || 3001}`);
console.log(`   SAP_AI_RESOURCE_GROUP: ${process.env.SAP_AI_RESOURCE_GROUP || 'default'}`);
console.log(`   AICORE_SERVICE_KEY: ${process.env.AICORE_SERVICE_KEY ? '✅ Configured' : '❌ Not configured (mock mode)'}`);

const server = new McpServer({
  name: 'backend-mcp-server',
  version: '1.0.0',
});

registerTools();

const app = express();

// Enable CORS for frontend (localhost:5173)
app.use(cors({
  origin: ['http://localhost:5173', 'http://localhost:3000'],
  credentials: true,
}));

app.use(express.json());

// Health check endpoint
app.get('/health', (_req: Request, res: Response) => {
  res.json({
    status: 'healthy',
    service: 'backend-mcp',
    version: '1.0.0',
    timestamp: new Date().toISOString(),
  });
});

// REST API routes for document management
app.use('/api/documents', documentRoutes);

// MCP endpoint
app.post('/mcp', async (req: Request, res: Response) => {
  const transport = new StreamableHTTPServerTransport({
    sessionIdGenerator: undefined,
    enableJsonResponse: true,
  });

  res.on('close', () => {
    transport.close();
  });

  await server.connect(transport);
  await transport.handleRequest(req, res, req.body);
});

const port = Number.parseInt(process.env.PORT ?? '3001', 10);

app
  .listen(port, () => {
    console.log(`Backend MCP Server running on http://localhost:${port}/mcp`);
  })
  .on('error', (error: unknown) => {
    console.error('Server error:', error);
    process.exit(1);
  });

function registerTools(): void {
  registerAddTool(server);
  registerWebSearchTool(server);
  registerWebResearchTool(server);
  // Only search is an MCP tool - upload/delete are REST API endpoints
  registerDocumentSearchTool(server);
  registerTimeAndPlaceTool(server);
  // S/4HANA Product API tools
  registerSearchProductDescriptionsTool(server);
  registerQueryProductsTool(server);
  registerProductApiTool(server);
  registerGetProductApiDocsTool(server);
  registerStockApiTool(server);
  // Memory tools
  registerMemoryLoadTool(server);
  registerMemorySaveTool(server);
  registerMemoryDeleteTool(server);
}
