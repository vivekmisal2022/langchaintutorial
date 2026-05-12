# DeepAgent Service Integration

The backend now supports **DeepAgent** mode with MCP (Model Context Protocol) tools integration for advanced agentic workflows.

## Architecture

The DeepAgent service follows the same pluggable architecture as the existing mock and LLM services:

```
backend/app/services/
├── mock_service.py          # Keyword-based mock responses
├── llm_service.py           # Simple LLM streaming
├── deepagent_service.py     # NEW: DeepAgent with MCP tools
└── service_factory.py       # Routes to appropriate service
```

## Service Selection

The backend automatically selects the appropriate service based on environment variables:

| MOCK_MODE | AGENTIC_MODE | Service Used |
|-----------|--------------|--------------|
| `true`    | (any)        | Mock Service |
| `false`   | `false`      | LLM Service  |
| `false`   | `true`       | **DeepAgent Service** |

## Configuration

### 1. Enable Agentic Mode

Update your `.env` file:

```bash
# Disable mock mode
MOCK_MODE=false

# Enable agentic mode
AGENTIC_MODE=true

# Ensure SAP AI Core credentials are configured
AICORE_BASE_URL=https://api.ai.prod.ap-northeast-1.aws.ml.hana.ondemand.com/v2
AICORE_AUTH_URL=https://...
AICORE_CLIENT_ID=...
AICORE_CLIENT_SECRET=...
AICORE_RESOURCE_GROUP=...
```

### 2. Start MCP Server

The DeepAgent service requires the MCP server to be running:

```bash
cd backend-mcp
pnpm install
pnpm dev
```

The MCP server should be accessible at `http://localhost:3001/mcp`.

### 3. Start Backend

```bash
cd backend
uv run uvicorn app.main:app --reload
```

## Features

### DeepAgent Capabilities

- **MCP Tools Integration**: Automatically loads tools from the MCP server (web search, calculations, etc.)
- **Streaming Responses**: Full SSE streaming support matching the existing API contract
- **Conversation History**: Maintains context across messages using session storage
- **Singleton Pattern**: Agent and model instances are cached for performance
- **Graceful Fallback**: Falls back to `ainvoke` if streaming produces no output

### Available MCP Tools

When the MCP server is running, the DeepAgent has access to:

- `add` - Simple addition tool (example)
- `web_search` - Quick web search using Perplexity Sonar
- `web_research` - Deep research using Perplexity Sonar Pro

## API Contract

The DeepAgent service maintains the same SSE streaming contract as other services:

### Request
```http
POST /api/chat-stream
Content-Type: application/json

{
  "message": "What is the stock price of SAP?",
  "session_id": "session-123"
}
```

### Response (SSE)
```
event: text
data: As of today, SAP's stock price is approximately...

event: text
data: $190.50 USD per share on NYSE.

event: end
data: 
```

## Implementation Details

### Singleton Pattern

The service uses singletons for:
- **Model Instance**: LLM model initialized once and reused
- **Agent Instance**: DeepAgent created once with tools
- **MCP Client**: Connection to MCP server maintained

This ensures:
- Fast response times (no re-initialization)
- Efficient resource usage
- Stable connections to MCP server

### Streaming Architecture

```python
async def generate_deepagent_response(message: str, session_id: str | None = None):
    # 1. Get or initialize agent (singleton)
    agent, _ = await _get_agent()
    
    # 2. Load conversation history
    conversation = load_history(session_id)
    conversation.append({"role": "user", "content": message})
    
    # 3. Stream response chunks
    async for chunk in agent.astream(payload, stream_mode="messages"):
        for text in _text_from_chunk(chunk):
            yield {"event": "text", "data": text}
    
    # 4. Signal end
    yield {"event": "end", "data": ""}
```

### Chunk Extraction

The service includes robust chunk extraction logic to handle various LangGraph output formats:
- Message objects with `.content` attribute
- Dictionary payloads with `messages` key
- Tuple wrapping `(channel, payload)`
- Structured content arrays

## Testing

### 1. Test with Mock Mode (No MCP Required)

```bash
# .env
MOCK_MODE=true
AGENTIC_MODE=false
```

```bash
curl -X POST http://localhost:8000/api/chat-stream \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello"}'
```

### 2. Test with LLM Mode

```bash
# .env
MOCK_MODE=false
AGENTIC_MODE=false
```

### 3. Test with DeepAgent Mode

```bash
# .env
MOCK_MODE=false
AGENTIC_MODE=true
```

Ensure MCP server is running first:
```bash
cd backend-mcp && pnpm dev
```

Then test:
```bash
curl -X POST http://localhost:8000/api/chat-stream \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the stock price of SAP? Use web search."}'
```

## Debugging

### Enable Debug Logging

```bash
# .env
LOG_LEVEL=DEBUG
```

### Check Agent Initialization

Look for these log messages:
```
INFO:app.services.deepagent_service:Initializing LLM model for DeepAgent
INFO:app.services.deepagent_service:Loaded 3 MCP tool(s)
INFO:app.services.deepagent_service:DeepAgent initialized successfully
```

### Verify MCP Connection

```bash
# Check MCP server is running
curl http://localhost:3001/mcp

# Should return MCP protocol response
```

### Use VS Code Debugger

The `.vscode/launch.json` includes a configuration for debugging the backend:

1. Set breakpoints in `deepagent_service.py`
2. Select "Debug FastAPI Backend" in VS Code
3. Press F5
4. Send requests from frontend or curl

## Frontend Integration

No changes required! The frontend automatically works with the DeepAgent service because it maintains the same SSE streaming API contract.

Simply:
1. Enable `AGENTIC_MODE=true` in backend `.env`
2. Start MCP server
3. Start backend
4. Use frontend normally

The frontend will receive streaming responses from the DeepAgent just like it does from the LLM service.

## Performance Notes

- **First Request**: ~2-3 seconds (agent initialization + MCP tool loading)
- **Subsequent Requests**: ~500ms-1s (cached agent + model)
- **MCP Tool Calls**: Add 1-3 seconds depending on tool (e.g., web search)

## Troubleshooting

### "Unable to load MCP tools"

**Cause**: MCP server not running or not accessible

**Solution**:
```bash
cd backend-mcp
pnpm dev
# Verify: curl http://localhost:3001/mcp
```

### "No streaming output"

**Cause**: Agent streaming may not produce output for simple queries

**Solution**: The service automatically falls back to `ainvoke` - check logs for "using invoke fallback"

### "DeepAgent Error: ..."

**Cause**: Various initialization or runtime errors

**Solution**:
1. Check `LOG_LEVEL=DEBUG` for detailed error messages
2. Verify SAP AI Core credentials in `.env`
3. Ensure `langchain_mcp_adapters` is installed: `uv sync`

## Migration from Prototype

The DeepAgent service is based on the `prototyping/deepagents_test.py` prototype with these adaptations:

1. **Async Generator**: Returns `AsyncGenerator[dict, None]` matching SSE contract
2. **Session Integration**: Uses `SessionStorage` for conversation history
3. **Singleton Pattern**: Caches agent/model for performance
4. **Error Handling**: Comprehensive error handling with SSE error events
5. **Logging**: Production-ready logging throughout

The prototype remains available for standalone CLI testing.
