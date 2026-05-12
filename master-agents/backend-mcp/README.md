# Backend MCP Server

This package hosts the TypeScript implementation of the backend Model Context Protocol server.

## Features

- **Document Ingestion Pipeline**: REST APIs to upload PDF/DOCX/TXT/MD files, view inventory, stream ingestion progress, and delete documents from HANA Cloud Vector Store
- **MCP Tools**: Extensible tool system with automatic logging (document search exposed as MCP tool)
- **Web Search**: Perplexity AI integration via SAP Generative AI Hub
- **SAP AI SDK**: Automatic OAuth2 authentication and deployment resolution
- **Mock Mode**: Fallback mode for testing without SAP infrastructure

## Prerequisites

- Node.js 20+
- pnpm (preferred package manager for this project)
- SAP AI Core service key (for web search functionality)

## Installation

```bash
pnpm install
```

## Configuration

Copy `.env.example` to `.env.local` and configure:

```bash
cp .env.example .env.local
```

Required for web search:
- `AICORE_SERVICE_KEY` - SAP AI Core service credentials (JSON string)
- `SAP_AI_RESOURCE_GROUP` - Resource group name (default: 'default')

See [`docs/README-SAP-AI-SDK-INTEGRATION.md`](./docs/README-SAP-AI-SDK-INTEGRATION.md) for detailed setup.

## Development

Start the server in watch mode:

```bash
pnpm dev
```

The server exposes both REST APIs (for application ingestion) on `http://localhost:3001/api/documents` and MCP endpoints (for LLM tooling) on `/mcp`.

## Build

Emit JavaScript to the `dist/` directory:

```bash
pnpm build
```

## Production Run

```bash
pnpm start
```

The server listens on `PORT` (default `3001`) and exposes the MCP endpoint at `/mcp`.

## Testing

Run SAP AI SDK integration tests:

```bash
pnpm test:sap
```

List available deployments:

```bash
pnpm list:deployments
```

See [`tests/README.md`](./tests/README.md) for more testing information.

## Project Structure

```
backend-mcp/
├── src/
│   ├── tools/          # MCP tools (add, web_search)
│   ├── resources/      # MCP resources
│   ├── utils/          # Logging and utilities
│   └── server.ts       # Main server
├── tests/              # Test scripts and logs
│   ├── test-sap-integration.ts
│   ├── list-deployments.ts
│   └── *.log
├── docs/               # Documentation
│   ├── README-WEB-SEARCH.md
│   ├── README-SAP-AI-SDK-INTEGRATION.md
│   ├── IMPLEMENTATION-SUMMARY.md
│   └── TEST-RESULTS.md
├── .env.example        # Environment template
└── package.json
```

## Documentation

- **Document Ingestion/API Guide**: this README (see “Document Management API” below)
- **User Guide**: [`docs/README-WEB-SEARCH.md`](./docs/README-WEB-SEARCH.md)
- **SAP Integration**: [`docs/README-SAP-AI-SDK-INTEGRATION.md`](./docs/README-SAP-AI-SDK-INTEGRATION.md)
- **Implementation**: [`docs/IMPLEMENTATION-SUMMARY.md`](./docs/IMPLEMENTATION-SUMMARY.md)
- **Test Results**: [`docs/TEST-RESULTS.md`](./docs/TEST-RESULTS.md)

## Document Management API

### 1. Upload & Ingest (async)

```
POST /api/documents/upload
multipart/form-data: files=@path/to/doc.pdf, tenant_id=tenant-a
```

- Accepts up to 10 files per request (`.pdf`, `.docx`, `.md`, `.txt`, `.doc`)
- Returns `202 Accepted` with one job per file:

```json
{
  "success": true,
  "message": "Accepted 1 document(s) for ingestion",
  "jobs": [
    {
      "job_id": "c4c8c1...",
      "filename": "financials.pdf",
      "status": "queued",
      "stage": "queued",
      "total_chunks": 0,
      "processed_chunks": 0,
      "created_at": "2025-11-16T15:42:18.123Z"
    }
  ]
}
```

### 2. Track Ingestion Progress

Polling endpoint:

```
GET /api/documents/progress/{job_id}
```

Server-Sent Events (live stream):

```
GET /api/documents/progress/{job_id}/stream
```

Each update includes `status`, `stage` (`queued | parsing | chunking | embedding | storing | completed | failed`), `totalChunks`, `processedChunks`, optional `message`, and error info when applicable. Use SSE endpoint to drive a frontend progress bar.

### 3. List Embedded Documents

```
GET /api/documents?tenant_id=tenant-a
```

Response:

```json
{
  "success": true,
  "documents": [
    {
      "document_id": "2024-financial-statements-en",
      "filename": "2024-financial-statements-en.pdf",
      "document_type": "pdf_document",
      "tenant_id": "tenant-a",
      "total_pages": 213,
      "chunk_count": 214,
      "last_ingested_at": "2025-11-15T15:43:03.362Z"
    }
  ]
}
```

### 4. Delete a Document

```
DELETE /api/documents/{document_id}?tenant_id=tenant-a
```

Deletes all chunks for that document (optionally filtered by tenant) and returns the number of chunks removed.

### 5. Search (also exposed as MCP tool `search_documents`)

```
POST /api/documents/search
{
  "query": "revenue guidance",
  "tenant_id": "tenant-a",
  "k": 4
}
```

Returns the top `k` chunks with metadata (including filename, page_number, chunk_id, and cosine similarity score). The MCP tool uses the same service for LLM retrieval workflows.

### Metadata Captured per Chunk

- `document_id`, `source_filename`, `document_type`, `tenant_id`
- Page-aware fields for PDFs/DOCX (`page_number`, `total_pages`)
- `chunk_id`, `chunk_index`, `total_chunks`
- Timestamp + user-supplied metadata (e.g., business unit) if provided in upload request.

## Available Tools

### `add`
Simple addition tool for testing MCP functionality.

### `web_search`
Quick web search using Perplexity Sonar. Best for straightforward queries.

**Example:**
```json
{
  "tool": "web_search",
  "arguments": {
    "query": "What are the latest AI developments?",
    "max_results": 5
  }
}
```

### `web_research`
Deep web research using Perplexity Sonar Pro. Best for complex research questions requiring in-depth investigation.

**Example:**
```json
{
  "tool": "web_research",
  "arguments": {
    "query": "Comprehensive analysis of AI impact on enterprise software development",
    "max_results": 5
  }
}
```

**Differences:**
- `web_search`: Fast, uses Sonar model, 1000 max tokens
- `web_research`: Comprehensive, uses Sonar Pro model, 2000 max tokens

See [`docs/README-WEB-SEARCH.md`](./docs/README-WEB-SEARCH.md) for detailed usage.
