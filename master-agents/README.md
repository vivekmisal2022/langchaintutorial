# Super Agent

AI-powered chat application with S/4HANA integration and MCP tool access. Uses Model Context Protocol (MCP) for intelligent, tool-augmented conversations.

## Features

- **Streaming AI Chat** — Real-time responses with markdown rendering and table display
- **Tool Status Indicators** — Live visibility into agent actions (web search, document lookup, etc.)
- **Document RAG** — Upload and search documents with semantic retrieval
- **Web Research** — Perplexity-powered web search and deep research
- **S/4HANA Product API** — Query product master data and material stock
- **Agent Memory** — Persistent memory across conversation sessions
- **Speech-to-Text** — Audio transcription using Gemini 2.5 Flash
- **Image Analysis** — Multimodal support for image attachments
- **Multi-User Support** — Session isolation with XSUAA authentication
- **Theme Support** — Light, Dark, and System theme modes

## Architecture

Three-service architecture:

| Service | Technology | Port |
|---------|------------|------|
| Frontend | React + Vite + UI5 | 5173 |
| Backend | FastAPI + Python | 8000 |
| Backend-MCP | Node.js + MCP SDK | 3001 |

See [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed documentation.

## Quick Start

### Prerequisites

- **Node.js** v22+
- **Python** 3.12+
- **uv** — [Install](https://docs.astral.sh/uv/getting-started/installation/)
- **pnpm** — [Install](https://pnpm.io/installation)
- **SAP BTP Account** with Generative AI Hub access

### 1. Clone & Setup

```bash
git clone <repository-url>
cd super-agent
```

### 2. Backend-MCP Setup

```bash
cd backend-mcp
pnpm install
cp .env.example .env.local
# Edit .env.local with your SAP credentials
pnpm dev
```

**Runs at:** http://localhost:3001

### 3. Backend Setup

```bash
cd backend
uv sync
cp .env.example .env
# Edit .env with your SAP credentials
uv run uvicorn app.main:app --reload --port 8000
```

**Runs at:** http://localhost:8000

### 4. Frontend Setup

```bash
cd frontend
pnpm install
pnpm dev
```

**Runs at:** http://localhost:5173

## Docker Build & Deploy

```bash
# Build and push all images
./build_and_push.sh

# Or build only
./build_and_push.sh build

# Deploy to Kubernetes (SAP BTP Kyma)
kubectl apply -f k8s/secret.yaml      # Secrets (not in git)
kubectl apply -f k8s/deployment.yaml  # All services
```

## Project Structure

```
super-agent/
├── frontend/              # React + Vite + UI5
├── backend/               # FastAPI + Python (DeepAgent orchestration)
├── backend-mcp/           # Node.js MCP server (tools + document API)
├── k8s/                   # Kubernetes deployment manifests
├── documentation/         # SDK examples and guides
├── design-documents/      # Original design specifications
├── ARCHITECTURE.md        # System architecture documentation
├── CLAUDE.md              # Claude Code guidance
└── build_and_push.sh      # Docker build script
```

## Service Modes

The backend supports three operation modes:

| Mode | Config | Description |
|------|--------|-------------|
| Mock | `MOCK_MODE=true` | Keyword-based responses for offline testing |
| LLM | `MOCK_MODE=false` | Simple streaming LLM (no tools) |
| Agentic | `AGENTIC_MODE=true` | DeepAgent with full MCP tool access |

## Environment Configuration

### Backend `.env`

```env
# Service Mode
MOCK_MODE=false
AGENTIC_MODE=true

# MCP Server
MCP_SERVER_URL=http://localhost:3001/mcp

# SAP Generative AI Hub
AICORE_SERVICE_KEY={"serviceurls":...}  # JSON service key

# LLM Configuration
LLM_MODEL=gpt-4.1
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=1000
```

### Backend-MCP `.env.local`

```env
# SAP Generative AI Hub
AICORE_SERVICE_KEY={"serviceurls":...}  # JSON service key

# HANA Cloud Vector Store
HANA_HOST=your-hana-host.hanacloud.ondemand.com
HANA_PORT=443
HANA_USER=your-user
HANA_PASSWORD=your-password

# Perplexity (via SAP AI Hub)
PERPLEXITY_DEPLOYMENT_ID=your-deployment-id
```

## MCP Tools

Tools available to the AI agent:

| Tool | Description |
|------|-------------|
| `search_document_headers` | Find relevant documents by summary |
| `search_document_content` | Semantic search within documents |
| `web_search` | Quick web search (Perplexity Sonar) |
| `web_research` | Deep research (Perplexity Sonar Pro) |
| `search_product_descriptions` | Search product descriptions semantically |
| `query_products` | Query S/4HANA product master data |
| `product_api` | Access S/4HANA Product API |
| `stock_api` | Access S/4HANA Material Stock API |
| `get_product_api_documentation` | Get Product API documentation |
| `memory_load` | Load persistent agent memory |
| `memory_save` | Save persistent agent memory |
| `memory_delete` | Delete persistent agent memory |
| `get_time_and_place` | Current time and location context |

## Testing

```bash
# Health checks
curl http://localhost:8000/health
curl http://localhost:3001/health

# Frontend
open http://localhost:5173
```

## Documentation

- [ARCHITECTURE.md](./ARCHITECTURE.md) — Full system architecture
- [CLAUDE.md](./CLAUDE.md) — Claude Code development guidance
- [backend/README_SERVICES.md](./backend/README_SERVICES.md) — Service factory pattern
- [backend-mcp/README.md](./backend-mcp/README.md) — MCP tools and document API

## Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, Vite, TypeScript, UI5 Web Components v2.x |
| Backend | FastAPI, Python 3.12, LangChain, DeepAgents |
| MCP Server | Node.js 20+, TypeScript, MCP SDK, Express |
| LLM | SAP Generative AI Hub (GPT-4.1, Gemini, Claude) |
| Vector DB | SAP HANA Cloud |
| Web Search | Perplexity via SAP AI Hub |
| Data | S/4HANA OData APIs |

## License

Proprietary - SAP Internal Use
