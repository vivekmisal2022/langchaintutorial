# Document Ingestion Service for HANA Cloud Vector Store

## Overview

The Document Ingestion Service provides a production-ready implementation for embedding documents into SAP HANA Cloud Vector Store with comprehensive metadata annotation and RAG best practices.

## Architecture

```
POST /api/documents/ingest
         ↓
    API Layer (documents.py)
         ↓
    Document Ingestion Service
         ↓
    ┌────────────────┴────────────────┐
    ↓                                 ↓
Text Splitting                 Metadata Enrichment
(RecursiveCharacterTextSplitter)    (LLM-generated)
    ↓                                 ↓
    └────────────────┬────────────────┘
                     ↓
         HANA Cloud Vector Store
         (with rich metadata)
```

## Key Features

### 1. **Metadata-First Architecture**
Following RAG best practices, each document chunk includes comprehensive metadata:

**Traceability Metadata:**
- `chunk_id`: Structured ID (tenant#document#chunk_000)
- `document_id`: Links chunks to parent document
- `filename`: Original filename
- `source_url`: File origin

**Structural Metadata:**
- `page_number`: Location in source document
- `section`: Document section/chapter
- `chunk_index`: Position in chunking sequence

**Domain Metadata:**
- `document_type`: Content classification
- `author`: Document author
- `created_at`: Document creation timestamp

**Enriched Metadata (LLM-generated):**
- `summary`: Concise chunk summary
- `keywords`: Extracted key terms
- `category`: LLM-assigned category

**Security Metadata:**
- `tenant_id`: Multi-tenant isolation

### 2. **Intelligent Text Splitting**

Uses LangChain's `RecursiveCharacterTextSplitter` with:
- **Chunk Size**: 1000 tokens (configurable)
- **Chunk Overlap**: 200 tokens (prevents context loss at boundaries)
- **Separators**: Prioritizes natural boundaries (paragraphs, sentences)

### 3. **LLM-Powered Metadata Enrichment**

Each chunk is analyzed by an LLM to generate:
- **Summary**: 2-3 sentence description
- **Keywords**: 3-5 key terms for hybrid search
- **Category**: Document classification

This enrichment enables:
- Better semantic search (summaries embedded with text)
- Hybrid search (keywords for BM25)
- Faceted filtering (categories)

### 4. **Multi-Tenant Support**

Every chunk includes `tenant_id` in metadata, enabling:
- Logical data isolation
- Tenant-scoped queries
- Future migration to native partitioning

### 5. **HANA Cloud Vector Store Integration**

Utilizes LangChain's `HanaDbVectorStore` with:
- **Embeddings**: SAP Generative AI Hub models
- **Connection**: HDBCLI client
- **Table**: Configurable table name
- **Distance**: Cosine similarity

## Configuration

### Environment Variables

```bash
# HANA Cloud Configuration
HANA_HOST=your-hana-host.hanacloud.ondemand.com
HANA_PORT=443
HANA_USER=your-username
HANA_PASSWORD=your-password
HANA_VECTOR_TABLE=DOCUMENT_VECTORS
HANA_ENCRYPT=true

# Embedding Model
EMBEDDING_MODEL=text-embedding-ada-002

# Chunking Configuration (Optional)
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
```

### pyproject.toml Dependencies

```toml
dependencies = [
    # ... existing dependencies
    "langchain-community>=0.3.31",
    "hdbcli>=2.21.28",
]
```

## API Usage

### Ingest Documents

```bash
POST /api/documents/ingest
Content-Type: application/json

{
  "contents": [
    "Financial report Q4 2024 content...",
    "Budget analysis document..."
  ],
  "metadatas": [
    {
      "filename": "q4_report.pdf",
      "source_url": "file:///reports/q4_report.pdf",
      "document_type": "financial_report",
      "author": "Finance Team",
      "created_at": "2024-01-15",
      "page_number": 1,
      "section": "Executive Summary"
    },
    {
      "filename": "budget_analysis.docx",
      "source_url": "file:///analyses/budget.docx",
      "document_type": "analysis"
    }
  ],
  "tenant_id": "workshop-2024"
}
```

### Response

```json
{
  "status": "success",
  "documents_processed": 2,
  "chunks_created": 5,
  "chunk_ids": [
    "workshop-2024#q4_report.pdf#chunk_000",
    "workshop-2024#q4_report.pdf#chunk_001",
    "workshop-2024#budget_analysis.docx#chunk_000",
    "workshop-2024#budget_analysis.docx#chunk_001",
    "workshop-2024#budget_analysis.docx#chunk_002"
  ]
}
```

## Data Model

### Gold Standard Schema

Each vector record in HANA Cloud contains:

```python
{
  # Identifiers
  "chunk_id": "tenant-123#doc-456#chunk_003",
  "document_id": "doc-456",
  
  # Traceability
  "filename": "financial_report.pdf",
  "source_url": "file:///uploads/financial_report.pdf",
  "page_number": 5,
  "section": "Revenue Analysis",
  
  # Domain
  "document_type": "financial_report",
  "author": "Finance Team",
  "created_at": "2024-10-15T10:30:00Z",
  
  # Position
  "chunk_index": 3,
  
  # Enriched (LLM-generated)
  "summary": "Analysis of Q3 revenue growth...",
  "keywords": ["revenue", "growth", "Q3", "YoY"],
  "category": "financial_analysis",
  
  # Security
  "tenant_id": "tenant-123"
}
```

## RAG Best Practices Implemented

### 1. **Tri-Modal Metadata Storage**

- **Dense Vector**: Summaries concatenated with text before embedding
- **Sparse Vector**: Keywords used for hybrid search (future enhancement)
- **Filter Fields**: Categorical metadata for pre-filtering

### 2. **Pre-Filtering Architecture**

The system is designed for **pre-filtering** (filter-then-search):
- Guarantees Top-K results matching tenant/filters
- Required for multi-tenant RAG
- HANA Cloud optimized for filtered queries

### 3. **Structured Chunking**

- Respects document structure (when available)
- Maintains context with overlap
- Preserves hierarchical relationships

### 4. **Metadata Enrichment Pipeline**

```
Document → Split → For Each Chunk:
                    1. Extract structural metadata
                    2. Generate LLM metadata (summary, keywords, category)
                    3. Concatenate summary with text
                    4. Embed enriched text
                    5. Store with complete metadata
```

## Advanced Retrieval Patterns

### Current Implementation: Enhanced Basic RAG

The current implementation provides a solid foundation with:
- Rich metadata for filtering
- Semantic search with embeddings
- Tenant isolation

### Future Enhancements

The architecture supports upgrade paths to:

1. **Parent-Child Retrieval**
   - Add `parent_id` field during ingestion
   - Store large parent chunks separately
   - Retrieve via small chunks, return large context

2. **Hybrid Search**
   - Use generated keywords for BM25 search
   - Combine with semantic search
   - Improves exact-match recall

3. **Self-Querying Retriever**
   - LLM extracts filters from natural language
   - Converts "last year's reports" → `created_at > 2024-01-01`

## Workshop Usage

### Simplified Setup for Workshops

1. **Use Simple Metadata**: Start with just `filename` and `document_type`
2. **Skip Enrichment**: Set `enrich_metadata=False` for faster ingestion
3. **Small Chunks**: Use `chunk_size=500` for quick demos

### Demo Flow

```python
# 1. Ingest sample documents
POST /api/documents/ingest
{
  "contents": ["Sample financial report..."],
  "metadatas": [{"filename": "sample.pdf"}],
  "tenant_id": "demo"
}

# 2. Query with filters (future retrieval endpoint)
GET /api/documents/search?query=revenue&tenant_id=demo
```

## Performance Considerations

### Ingestion Time

- **Small document** (1 page): ~2-3 seconds
- **Medium document** (10 pages): ~10-15 seconds
- **Large document** (100 pages): ~2-3 minutes

Time breakdown:
- Text splitting: 10%
- LLM enrichment: 60% (bulk of time)
- Embedding + storage: 30%

### Optimization Tips

1. **Batch Processing**: Process multiple documents in parallel
2. **Skip Enrichment**: For non-critical documents, disable LLM enrichment
3. **Cached Embeddings**: Reuse embeddings for duplicate content
4. **Async Processing**: Use background tasks for large ingestion jobs

## Testing

```bash
# Run tests
cd backend
uv run pytest tests/test_document_ingestion.py -v

# Test with real HANA Cloud (requires credentials)
uv run pytest tests/test_document_ingestion.py --hana-integration
```

## Troubleshooting

### "Unable to connect to HANA Cloud"

**Cause**: Invalid credentials or network issues

**Solution**:
1. Verify credentials in `.env`
2. Test connection: `uv run python -c "import hdbcli; print('OK')"`
3. Check firewall/VPN settings

### "Embedding generation failed"

**Cause**: SAP AI Core credentials or model issues

**Solution**:
1. Verify AI Core credentials
2. Check model availability: `EMBEDDING_MODEL=text-embedding-ada-002`
3. Test with simple LLM call first

### "Metadata enrichment takes too long"

**Cause**: LLM calls are slow

**Solution**:
1. Use faster model: `SUMMARIZATION_LLM_MODEL=gpt-3.5-turbo`
2. Disable enrichment: `enrich_metadata=False` in API call
3. Process documents in background tasks

## Security Considerations

### Multi-Tenant Isolation

- **Logical Isolation**: Every chunk tagged with `tenant_id`
- **Query Scope**: All retrievals must filter by `tenant_id`
- **Future**: Migrate to HANA native partitioning for physical isolation

### Data Privacy

- Documents stored in HANA Cloud (customer-controlled)
- Metadata enrichment uses SAP AI Core (EU data center)
- No data sent to third-party services

## Migration Path

### From Simple to Advanced

1. **Phase 1** (Current): Basic RAG with rich metadata
2. **Phase 2**: Add hybrid search (BM25 + semantic)
3. **Phase 3**: Implement parent-child retrieval
4. **Phase 4**: Add self-querying retriever
5. **Phase 5**: Native HANA partitioning for multi-tenancy

Each phase builds on the metadata foundation established in Phase 1.

## References

- [LangChain HANA Vector Store](https://python.langchain.com/docs/integrations/vectorstores/sap_hanavector)
- [SAP HANA Cloud Vector Engine](https://help.sap.com/docs/hana-cloud-database/sap-hana-cloud-sap-hana-database-vector-engine-guide/sap-hana-cloud-sap-hana-database-vector-engine-guide)
- [RAG Best Practices Paper](https://arxiv.org/abs/2312.10997)

## Support

For issues or questions:
1. Check logs: `LOG_LEVEL=DEBUG` in `.env`
2. Review test cases in `tests/test_document_ingestion.py`
3. Consult LangChain documentation for HANA integration
