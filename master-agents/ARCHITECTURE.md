# Super Agent - Architecture

## Overview

Super Agent is an AI-powered chat application with S/4HANA integration that leverages the **Model Context Protocol (MCP)** to provide intelligent, tool-augmented conversations. It combines a modern React frontend with a Python backend orchestrating LLM interactions, and a separate Node.js MCP server providing specialized tools for document retrieval, web research, and S/4HANA data access.

---

## System Components

### 1. Frontend (React + Vite + UI5)

**Technology Stack:** React 18, Vite, TypeScript, SAP UI5 Web Components v2.x (Fiori Horizon theme)

**Port:** `localhost:5173`

The frontend provides a Fiori-style chat interface with the following capabilities:

- **Chat Interface** — Real-time streaming responses with markdown rendering and table display
- **Tool Status Indicators** — Live display of active tool calls (e.g., "Searching the web...")
- **Document Management** — Upload, view, and delete documents for RAG (Retrieval-Augmented Generation)
- **Audio Input** — Speech-to-text transcription using Gemini 2.5 Flash
- **Image Attachments** — Multimodal support for image analysis
- **Chat History** — Session persistence with automatic title generation
- **Theme Support** — Light, Dark, and System theme modes

**Key Components:**

| Component | Purpose |
|-----------|---------|
| `AppShell` | Main layout with sidebar and content area |
| `ChatInterface` | Orchestrates chat input and message display |
| `ChatInput` | Text, audio recording, and file attachments |
| `ChatMessages` | Renders streaming AI responses with markdown |
| `ToolStatusIndicator` | Displays active tool calls during streaming |
| `DocumentManagement` | UI for document upload/delete/search |
| `ChatHistorySidebar` | Lists and manages chat sessions |

---

### 2. Backend (FastAPI + Python)

**Technology Stack:** FastAPI, Python 3.12+, LangChain, DeepAgents, SAP Generative AI Hub SDK

**Port:** `localhost:8000`

The backend acts as the orchestration layer between the frontend and AI services. It implements a **pluggable service architecture** with three modes:

#### Service Modes

| Mode | Environment Variable | Description |
|------|---------------------|-------------|
| **Mock** | `MOCK_MODE=true` | Keyword-based responses for offline testing |
| **LLM** | `MOCK_MODE=false` | Simple streaming LLM (no tools) |
| **Agentic** | `AGENTIC_MODE=true` | DeepAgent with full MCP tool access |

#### Core Services

- **Service Factory** — Routes requests to the appropriate service based on configuration
- **DeepAgent Service** — LangGraph-based agent that connects to MCP tools via HTTP
- **LLM Service** — Direct streaming responses from SAP Generative AI Hub
- **Session Storage** — JSON file-based persistence for chat history (per-user isolation)
- **Audio Transcription** — Converts speech to text using Gemini models
- **Title Generation** — Auto-generates chat titles using LLM

#### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/chat-stream` | POST | Stream chat responses (SSE) |
| `/api/sessions` | GET/POST/DELETE | Manage chat sessions |
| `/api/audio/transcribe` | POST | Transcribe audio files |
| `/health` | GET | Health check |

#### SSE Event Types

The chat stream uses Server-Sent Events with the following event types:

| Event | Description |
|-------|-------------|
| `text` | Streaming text content |
| `table` | JSON table data (columns + rows) |
| `tool_start` | Tool invocation started (tool_id, tool_name, args) |
| `tool_end` | Tool invocation completed (tool_id, success) |
| `error` | Error message |
| `end` | Stream completion |

---

### 3. Backend-MCP (Node.js + TypeScript)

**Technology Stack:** Node.js 20+, TypeScript, MCP SDK, Express

**Port:** `localhost:3001`

The MCP server exposes tools that the DeepAgent can invoke during conversations. It provides both **MCP tools** (for LLM use) and **REST APIs** (for frontend use).

#### MCP Tools (Invoked by LLM)

| Tool | Description |
|------|-------------|
| `search_document_headers` | Search document summaries to find relevant documents |
| `search_document_content` | Semantic search within document chunks |
| `web_search` | Quick web search via Perplexity Sonar |
| `web_research` | Deep research via Perplexity Sonar Pro |
| `search_product_descriptions` | Search product descriptions semantically |
| `query_products` | Query S/4HANA product master data |
| `product_api` | Access S/4HANA Product API |
| `stock_api` | Access S/4HANA Material Stock API |
| `get_product_api_documentation` | Get Product API documentation |
| `memory_load` | Load persistent agent memory |
| `memory_save` | Save persistent agent memory |
| `memory_delete` | Delete persistent agent memory |
| `get_time_and_place` | Get current time and location context |

#### REST APIs (Called by Frontend)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/documents/upload` | POST | Upload and ingest documents |
| `/api/documents` | GET | List ingested documents |
| `/api/documents/:id` | DELETE | Delete a document |
| `/api/documents/progress/:id` | GET | Track ingestion progress |
| `/api/documents/search` | POST | Search documents |

#### Document Ingestion Pipeline

1. **Upload** — Accept PDF, DOCX, TXT, MD files
2. **Parse** — Extract text content (with VLM for PDF images)
3. **Chunk** — Split into semantic chunks
4. **Embed** — Generate embeddings via SAP AI Hub
5. **Store** — Save to HANA Cloud Vector Store

---

### 4. External Services

#### SAP Generative AI Hub

The primary AI infrastructure providing:

- **LLM Access** — GPT-4.1, Gemini 2.5 Flash, Claude models
- **Embedding Models** — For document vectorization
- **Perplexity Proxy** — Web search capabilities via Sonar/Sonar Pro

**Configuration:** Requires `AICORE_SERVICE_KEY` with OAuth2 credentials

#### SAP HANA Cloud Vector Store

Stores document embeddings for semantic search:

- **Header Table** — Document metadata and summaries
- **Chunks Table** — Individual text chunks with embeddings
- **Cosine Similarity** — Vector search for RAG retrieval

---

## Communication Patterns

### Chat Request Flow

```
User → Frontend → POST /api/chat-stream → Service Factory
                                              ↓
                              ┌───────────────┼───────────────┐
                              ↓               ↓               ↓
                           Mock           LLM Only        DeepAgent
                              ↓               ↓               ↓
                         Keywords      SAP AI Hub     MCP Client → MCP Server
                                                                      ↓
                                                              ┌───────┴───────┐
                                                              ↓       ↓       ↓
                                                           HANA   Perplexity  S/4
                              ↓               ↓               ↓
                              └───────────────┴───────────────┘
                                              ↓
                                     SSE Stream → Frontend → User
```

### Tool Status Flow

```
DeepAgent decides to call tool
         ↓
Backend emits: tool_start event (tool_name, tool_id)
         ↓
Frontend shows: "🔍 Searching the web..."
         ↓
MCP Server executes tool
         ↓
Backend emits: tool_end event (tool_id, success)
         ↓
Frontend hides status indicator
         ↓
Backend streams: text response
```

### Document RAG Flow

```
User Question → DeepAgent
                   ↓
         search_document_headers (MCP)
                   ↓
              HANA Vector Search (summaries)
                   ↓
         search_document_content (MCP)
                   ↓
              HANA Vector Search (chunks)
                   ↓
         Context + Question → LLM
                   ↓
              Answer → User
```

### Document Ingestion Flow

```
Frontend → POST /api/documents/upload
              ↓
         Backend-MCP
              ↓
    ┌─────────┴─────────┐
    ↓                   ↓
  Parse              Chunk
    ↓                   ↓
    └─────────┬─────────┘
              ↓
        Generate Embeddings (SAP AI Hub)
              ↓
        Store in HANA Vector Store
              ↓
        Return Success
```

---

## Key Design Decisions

### Separation of Concerns

- **MCP Tools** — Read-only operations for LLM to retrieve information
- **REST APIs** — CRUD operations for applications to manage data
- **Service Factory** — Easily switch between mock/LLM/agentic modes

### Streaming Architecture

- **Server-Sent Events (SSE)** — Real-time streaming from backend to frontend
- **LangGraph Streaming** — Token-by-token output from DeepAgent
- **Tool Status Events** — Real-time visibility into agent actions

### Multi-User Support

- Sessions isolated by user ID (extracted from JWT tokens)
- Per-user chat history storage
- Documents can be isolated by `tenant_id`

### Kubernetes Deployment

The application is designed for deployment on SAP BTP Kyma:

- **Three deployments**: frontend, backend, backend-mcp
- **SAP App Router**: Authentication via XSUAA
- **Istio**: Service mesh with SSE-friendly timeouts
- **Persistent storage**: PVC for session data

---

## Technology Summary

| Layer | Technology | Purpose |
|-------|------------|---------|
| Frontend | React + Vite + UI5 | User interface |
| Backend | FastAPI + Python | API orchestration |
| Agent | LangGraph + DeepAgents | Agentic AI workflows |
| MCP Server | Node.js + MCP SDK | Tool execution |
| LLM | SAP Generative AI Hub | Language models |
| Vector DB | HANA Cloud | Document embeddings |
| Web Search | Perplexity via SAP | Research capabilities |
| Data | S/4HANA OData | Product & stock data |

---

## Getting Started

### Local Development

1. **Start Backend-MCP:** `cd backend-mcp && pnpm dev` (port 3001)
2. **Start Backend:** `cd backend && uv run uvicorn app.main:app --reload` (port 8000)
3. **Start Frontend:** `cd frontend && pnpm dev` (port 5173)

Configure `.env` files in each directory with appropriate SAP credentials.

### Docker Build

```bash
./build_and_push.sh          # Build and push all images
./build_and_push.sh build    # Build only
./build_and_push.sh push     # Push only
```

### Kubernetes Deployment

```bash
kubectl apply -f k8s/secret.yaml      # Apply secrets (not in git)
kubectl apply -f k8s/deployment.yaml  # Deploy all services
```

---

## Related Documentation

- [Backend Services](./backend/README_SERVICES.md) — Service factory pattern
- [MCP Server](./backend-mcp/README.md) — Tools and API reference
- [Design Documents](./design-documents/) — Initial specifications
