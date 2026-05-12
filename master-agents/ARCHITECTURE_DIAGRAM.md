# Super Agent Architecture Diagram

```mermaid
---
config:
  layout: elk
---
flowchart TB
 subgraph User["👤 User"]
        Browser["Web Browser"]
  end
 subgraph Frontend["Frontend (React + Vite + UI5)"]
    direction TB
        AppShell["AppShell"]
        ChatInterface["Chat Interface"]
        ChatInput["Chat Input<br>(Text + Audio + Images)"]
        ChatMessages["Chat Messages<br>(Markdown + Tables)"]
        DocMgmt["Document Management"]
        ChatHistory["Chat History Sidebar"]
        ThemeProvider["Theme Provider"]
  end
 subgraph Services["Service Layer"]
        ServiceFactory["Service Factory"]
        MockService["Mock Service<br>(Keyword-based)"]
        LLMService["LLM Service<br>(Simple streaming)"]
        DeepAgentService["DeepAgent Service<br>(Agentic + MCP Tools)"]
  end
 subgraph APIs["API Routes"]
        ChatAPI["Chat Stream API<br>/api/chat-stream"]
        HistoryAPI["History API<br>/api/sessions"]
        AudioAPI["Audio API<br>/api/audio/transcribe"]
  end
 subgraph Backend["Backend (FastAPI + Python)"]
    direction TB
        MainApp["FastAPI App<br>:8000"]
        Services
        APIs
        SessionStorage["Session Storage<br>(JSON files)"]
        TitleGeneration["Title Generation"]
        AudioTranscription["Audio Transcription"]
  end
 subgraph MCPTools["MCP Tools (for LLM)"]
        DocSearchTool["Document Search Tools<br>• search_document_headers<br>• search_document_content"]
        WebSearchTool["Web Search Tools<br>• web_search (Sonar)<br>• web_research (Sonar Pro)"]
        ODataTools["S/4HANA Tools<br>• search_product_descriptions<br>• query_products<br>• product_api<br>• stock_api<br>• get_product_api_documentation"]
        UtilTools["Utility Tools<br>• get_time_and_place<br>• memory_load<br>• memory_save<br>• memory_delete"]
  end
 subgraph RESTAPIs["REST APIs (for Frontend)"]
        DocUpload["POST /api/documents/upload"]
        DocList["GET /api/documents"]
        DocDelete["DELETE /api/documents/:id"]
        DocProgress["GET /api/documents/progress/:id"]
  end
 subgraph BackendMCP["Backend-MCP (Node.js + TypeScript)"]
    direction TB
        MCPServer["MCP Server<br>:3001"]
        MCPTools
        RESTAPIs
        DocIngestionService["Document Ingestion Service<br>(Chunking + Embedding)"]
  end
 subgraph SAPAI["SAP Generative AI Hub"]
        LLMs["LLM Models<br>• GPT-4.1<br>• Gemini 2.5 Flash<br>• Claude"]
        PerplexityProxy["Perplexity AI Proxy<br>(Sonar/Sonar Pro)"]
  end
 subgraph ExternalServices["External Services"]
    direction TB
        SAPAI
        HANAVector["SAP HANA Cloud<br>Vector Store"]
        SAPBW["S/4HANA<br>OData APIs"]
  end
    Browser --> Frontend
    ChatInterface --> ChatAPI
    ChatInput --> ChatAPI & AudioAPI
    DocMgmt --> DocUpload & DocList & DocDelete & DocProgress
    ChatHistory --> HistoryAPI
    ChatAPI --> ServiceFactory & SessionStorage & TitleGeneration
    ServiceFactory --> MockService & LLMService & DeepAgentService
    HistoryAPI --> SessionStorage
    AudioAPI --> AudioTranscription
    DeepAgentService -- MCP Protocol<br>(HTTP) --> MCPServer
    MCPServer --> DocSearchTool & WebSearchTool & ODataTools & UtilTools & DocIngestionService
    LLMService --> LLMs
    DeepAgentService --> LLMs
    TitleGeneration --> LLMs
    AudioTranscription --> LLMs
    WebSearchTool --> PerplexityProxy
    DocSearchTool --> HANAVector
    DocIngestionService --> HANAVector
    ODataTools --> SAPBW

     Browser:::frontend
     AppShell:::frontend
     ChatInterface:::frontend
     ChatInput:::frontend
     ChatMessages:::frontend
     DocMgmt:::frontend
     ChatHistory:::frontend
     ThemeProvider:::frontend
     MainApp:::backend
     ServiceFactory:::backend
     MockService:::backend
     LLMService:::backend
     DeepAgentService:::backend
     ChatAPI:::backend
     HistoryAPI:::backend
     AudioAPI:::backend
     SessionStorage:::backend
     TitleGeneration:::backend
     AudioTranscription:::backend
     MCPServer:::mcp
     DocSearchTool:::mcp
     WebSearchTool:::mcp
     ODataTools:::mcp
     UtilTools:::mcp
     DocUpload:::mcp
     DocList:::mcp
     DocDelete:::mcp
     DocProgress:::mcp
     DocIngestionService:::mcp
     LLMs:::external
     PerplexityProxy:::external
     HANAVector:::external
     SAPBW:::external
    classDef frontend fill:#61dafb,stroke:#333,color:#000
    classDef backend fill:#009688,stroke:#333,color:#fff
    classDef mcp fill:#ff9800,stroke:#333,color:#000
    classDef external fill:#9c27b0,stroke:#333,color:#fff
    classDef user fill:#4caf50,stroke:#333,color:#fff
```

## Legend

| Color | Component Type |
|-------|----------------|
| 🔵 Cyan | Frontend (React/UI5) |
| 🟢 Teal | Backend (FastAPI/Python) |
| 🟠 Orange | Backend-MCP (Node.js/MCP Server) |
| 🟣 Purple | External Services |

## Key Data Flows

1. **Chat Flow**: User → Frontend → Backend API → Service Factory → LLM/DeepAgent → Response
2. **Document Upload**: Frontend → Backend-MCP REST API → Chunking → Embedding → HANA Vector Store
3. **Document RAG**: DeepAgent → MCP Tool → HANA Vector Search → Context → LLM Response
4. **Web Research**: DeepAgent → MCP Tool → SAP AI Hub → Perplexity API → Research Results
5. **Audio Transcription**: Frontend → Backend API → SAP AI Hub → Gemini → Text
