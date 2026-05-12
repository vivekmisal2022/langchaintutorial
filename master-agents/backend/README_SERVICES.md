# Backend Services Architecture

## Overview

The Super Agent backend uses a **modular, pluggable architecture** that allows you to easily switch between different chat response services:

1. **Mock Service** - For testing without LLM (keyword-based responses)
2. **LLM Service** - Simple streaming LLM using SAP Generative AI Hub
3. **Agentic Service** - Full agent with MCP tools and RAG

## How It Works

### Service Factory Pattern

The `service_factory.py` acts as a router that automatically selects the appropriate service based on your `.env` configuration:

```
┌─────────────────┐
│  Chat Endpoint  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Service Factory │ ◄── Reads MOCK_MODE from .env
└────────┬────────┘
         │
    ┌────┴────┬──────────┬──────────────┐
    ▼         ▼          ▼              ▼
┌────────┐ ┌─────┐  ┌─────────┐  ┌──────────┐
│  Mock  │ │ LLM │  │ Agentic │  │  Future  │
│Service │ │Svc  │  │ Service │  │ Services │
└────────┘ └─────┘  └─────────┘  └──────────┘
```

## Switching Between Services

### 1. Mock Service (Default)

**Use Case:** Testing, workshops, offline development

**Configuration (.env):**
```bash
MOCK_MODE=true
```

**Features:**
- Keyword-based responses
- Simulated table data for "excel", "product", "sales" keywords
- No external dependencies
- Instant responses

### 2. LLM Service

**Use Case:** Real AI responses with streaming

**Configuration (.env):**
```bash
MOCK_MODE=false

# SAP Generative AI Hub credentials
AICC_BASE_URL=https://api.ai.prod.ap-northeast-1.aws.ml.hana.ondemand.com/v2
AICC_AUTH_URL=https://your-auth-url.ondemand.com/oauth/token
AICC_CLIENT_ID=your-client-id
AICC_CLIENT_SECRET=your-client-secret
AICC_RESOURCE_GROUP=your-resource-group
```

**Features:**
- Real LLM responses (GPT-4o-mini by default)
- Streaming text generation
- Uses SAP Generative AI Hub SDK
- No tools or complex agentic behavior (simple Q&A)

**Model Options:**
You can change the model in `llm_service.py`:
- `gpt-4o-mini` (default, cost-effective)
- `gpt-4o`
- `gemini-2.0-flash`
- `anthropic--claude-3-haiku`

### 3. Agentic Service

**Use Case:** Complex workflows with MCP tools, RAG, and multi-step reasoning

**Configuration (.env):**
```bash
MOCK_MODE=false
AGENTIC_MODE=true
```

**Features:**
- DeepAgent with MCP tool integration
- Document retrieval (RAG)
- Web search capabilities
- Multi-step reasoning

## File Structure

```
backend/app/services/
├── __init__.py
├── mock_service.py          # Keyword-based mock responses
├── llm_service.py            # Simple LLM streaming (NEW)
├── service_factory.py        # Service router (NEW)
└── session_storage.py        # Chat history persistence
```

## Adding a New Service

To add a new service (e.g., agentic service):

1. **Create service file:**
   ```python
   # app/services/agentic_service.py
   async def generate_agentic_response(message: str, session_id: str | None = None):
       # Your implementation
       yield {"event": "text", "data": "..."}
       yield {"event": "end", "data": ""}
   ```

2. **Update service factory:**
   ```python
   # app/services/service_factory.py
   from app.services.agentic_service import generate_agentic_response
   
   # Add to get_service_type() logic
   # Add to generate_response() routing
   ```

3. **Add configuration:**
   ```python
   # app/core/config.py
   agentic_mode: bool = False
   ```

## Testing

### Test Mock Service
```bash
# Set MOCK_MODE=true in .env
curl -X POST http://localhost:8000/api/chat-stream \
  -H "Content-Type: application/json" \
  -d '{"message": "show me products", "session_id": "test"}'
```

### Test LLM Service
```bash
# Set MOCK_MODE=false in .env with valid credentials
curl -X POST http://localhost:8000/api/chat-stream \
  -H "Content-Type: application/json" \
  -d '{"message": "What is SAP Fiori?", "session_id": "test"}'
```

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MOCK_MODE` | No | `true` | Enable mock service |
| `AICC_BASE_URL` | Yes (LLM) | - | SAP AI Core base URL |
| `AICC_AUTH_URL` | Yes (LLM) | - | OAuth token URL |
| `AICC_CLIENT_ID` | Yes (LLM) | - | OAuth client ID |
| `AICC_CLIENT_SECRET` | Yes (LLM) | - | OAuth client secret |
| `AICC_RESOURCE_GROUP` | No | `default` | AI Core resource group |

## Workshop Usage

For workshop participants:

1. **Start with Mock Mode** - No credentials needed
2. **Demo LLM Mode** - Use instructor credentials
3. **Show Modularity** - Switch between modes by changing one env var

This architecture makes it easy to demonstrate different capabilities without changing code!
