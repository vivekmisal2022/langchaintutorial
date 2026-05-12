# Document Management Feature

## Overview
The Document Management feature allows users to upload, view, and delete documents that are embedded into a HANA Cloud Vector Store for RAG (Retrieval-Augmented Generation) in chat conversations.

## Features

### ✅ Implemented
- **Navigation**: Toggle between Chat and Document Management views
- **Upload Queue**: Multiple file upload with sequential processing
- **Progress Tracking**: Real-time progress bar via Server-Sent Events
- **Document List**: View all uploaded documents with metadata
- **Delete**: Remove documents and their embeddings
- **Search**: Filter documents by filename
- **Empty State**: Helpful UI when no documents exist
- **Error Handling**: User-friendly error messages and toast notifications
- **Theme Support**: Works with light/dark/system themes

## Architecture

### Frontend Components

#### 1. **AppShell** (`src/components/AppShell.tsx`)
- Added navigation buttons (Chat / Documents) in ShellBar
- Conditionally renders ChatInterface or DocumentManagement
- Hides sidebar when in document management mode

#### 2. **DocumentManagement** (`src/components/DocumentManagement.tsx`)
Main component with:
- File upload button and hidden file input
- Upload queue with progress indicators
- Search input for filtering documents
- Table displaying document metadata
- Delete actions with confirmation
- Empty state when no documents

#### 3. **API Service** (`src/services/documents.ts`)
Functions for:
- `uploadDocument(file, tenantId?)` - Upload single file
- `listDocuments(tenantId?)` - Get all documents
- `deleteDocument(documentId, tenantId?)` - Delete document
- `getJobProgress(jobId)` - Poll job status
- `streamJobProgress(jobId, callbacks)` - SSE for real-time updates

#### 4. **Types** (`src/types/index.ts`)
New types:
- `UploadJob` - Job status and progress
- `DocumentInfo` - Document metadata
- `QueuedUpload` - Frontend upload queue item
- `JobStatus`, `JobStage` - Status enums

## User Flow

### Upload Documents

1. User clicks "Upload Document" button
2. File picker opens (accepts `.pdf`, `.docx`, `.md`, `.txt`, `.doc`)
3. User selects one or more files
4. Files added to upload queue with "Queued" status
5. Frontend processes queue sequentially:
   - Upload file to backend (`POST /api/documents/upload`)
   - Backend returns job ID
   - Frontend opens SSE stream (`GET /api/documents/progress/{job_id}/stream`)
   - Progress bar updates through stages:
     - Queued (0%)
     - Uploading (10%)
     - Parsing (30%)
     - Chunking (40%)
     - Embedding (40-80% based on chunks processed)
     - Storing (90%)
     - Completed (100%)
6. On completion, document list refreshes
7. Queue item removed after 2-second delay
8. Next queued file starts processing

### View Documents

1. Documents displayed in table with columns:
   - Name (filename)
   - Upload Date
   - Type (pdf, docx, etc.)
   - Chunks (number of embedded chunks)
   - Actions (delete button)
2. Search bar filters by filename
3. Empty state shown when no documents

### Delete Documents

1. User clicks delete icon
2. Confirmation dialog appears
3. On confirm, `DELETE /api/documents/{documentId}` called
4. Document and all chunks removed from vector store
5. Toast notification shows success
6. Document list refreshes

## Backend API Integration

### Endpoints Used

#### 1. Upload Document
```
POST /api/documents/upload
Content-Type: multipart/form-data

Body:
- files: File[]
- tenant_id: string (optional)

Response: 202 Accepted
{
  "success": true,
  "message": "Accepted 1 document(s) for ingestion",
  "jobs": [
    {
      "job_id": "uuid",
      "filename": "doc.pdf",
      "status": "queued",
      "stage": "queued",
      "total_chunks": 0,
      "processed_chunks": 0,
      "created_at": "2025-11-17T..."
    }
  ]
}
```

#### 2. Stream Progress (SSE)
```
GET /api/documents/progress/{job_id}/stream

Response: text/event-stream
data: {"job_id":"uuid","status":"running","stage":"embedding",...}
data: {"job_id":"uuid","status":"completed","stage":"completed",...}
event: done
data: {"job_id":"uuid"}
```

#### 3. List Documents
```
GET /api/documents?tenant_id=optional

Response: 200 OK
{
  "success": true,
  "documents": [
    {
      "document_id": "doc-id",
      "source_filename": "file.pdf",
      "created_at": "2025-11-17T...",
      "document_type": "pdf",
      "total_chunks": 42,
      "tenant_id": "default"
    }
  ]
}
```

#### 4. Delete Document
```
DELETE /api/documents/{documentId}?tenant_id=optional

Response: 200 OK
{
  "success": true,
  "document_id": "doc-id",
  "chunks_deleted": 42
}
```

## Configuration

### Environment Variables

Add to `frontend/.env`:
```bash
# Document Management API URL (MCP backend)
VITE_DOCUMENT_API_URL=http://localhost:3001
```

### Supported File Types
- PDF (`.pdf`)
- Word (`.docx`, `.doc`)
- Markdown (`.md`)
- Text (`.txt`)

**Note**: PowerPoint (`.pptx`) support pending backend implementation.

## Upload Queue Logic

### Sequential Processing
- Backend processes one document at a time
- Frontend queues multiple uploads
- Only one upload active at any time
- Uses `processingRef` to prevent concurrent processing

### Progress Calculation
```typescript
Stage → Progress
queued → 0%
uploading → 10%
parsing → 30%
chunking → 40%
embedding → 40-80% (based on chunks processed)
storing → 90%
completed → 100%
```

### Error Handling
- Upload errors: Show in queue item, continue to next
- SSE errors: Close stream, mark as failed, continue to next
- Delete errors: Show MessageStrip at top
- Network errors: Caught and displayed to user

## UI Components Used

All UI5 Web Components v2.x:
- `ShellBar` - Top navigation
- `Button` - Actions and navigation
- `FlexBox` - Layout
- `Title`, `Text`, `Label` - Typography
- `Input` - Search
- `Table`, `TableHeaderRow`, `TableHeaderCell`, `TableRow`, `TableCell` - Document list (v2 API)
- `ProgressIndicator` - Upload progress
- `MessageStrip` - Error messages
- `Toast` - Success notifications
- Icons: `upload`, `delete`, `search`, `document`, `discussion`

**Note**: UI5 Web Components v2 changed the Table API. Use `headerRow` prop with `TableHeaderRow` and `TableHeaderCell` components instead of the v1 `columns` prop.

## Theme Support

Uses SAP theme variables:
- `--sapBackgroundColor`
- `--sapGroup_ContentBackground`
- `--sapGroup_BorderColor`
- `--sapList_BorderColor`
- `--sapContent_LabelColor`
- `--sapContent_IconColor`
- `--sapNegativeColor` (errors)

Works seamlessly with light/dark/system themes.

## Testing Checklist

### Upload Flow
- [ ] Click "Upload Document" opens file picker
- [ ] Select single file → added to queue
- [ ] Select multiple files → all added to queue
- [ ] Files process sequentially (one at a time)
- [ ] Progress bar updates through stages
- [ ] Completed files removed from queue after delay
- [ ] Document list refreshes after completion
- [ ] Unsupported file types rejected

### Document List
- [ ] Documents load on page mount
- [ ] Table shows all document metadata
- [ ] Search filters by filename
- [ ] Empty state shows when no documents
- [ ] Dates formatted correctly

### Delete
- [ ] Click delete shows confirmation
- [ ] Confirm deletes document
- [ ] Cancel does nothing
- [ ] Toast shows success message
- [ ] Document list refreshes

### Error Handling
- [ ] Upload errors shown in queue
- [ ] Network errors shown in MessageStrip
- [ ] SSE connection errors handled gracefully
- [ ] Failed uploads don't block queue

### Navigation
- [ ] Chat/Documents buttons toggle views
- [ ] Sidebar hidden in document view
- [ ] Sidebar shown in chat view
- [ ] Active button highlighted

### Theme
- [ ] Works in light theme
- [ ] Works in dark theme
- [ ] Works in system theme
- [ ] Theme toggle persists

## Future Enhancements

### Potential Features
- [ ] Bulk delete (select multiple documents)
- [ ] Document preview/download
- [ ] Metadata editing (tags, description)
- [ ] Tenant selector UI
- [ ] Upload from URL
- [ ] Drag-and-drop upload
- [ ] File size display
- [ ] Retry failed uploads
- [ ] Pause/resume uploads
- [ ] Upload history/logs
- [ ] Document statistics dashboard

### Performance Optimizations
- [ ] Pagination for large document lists
- [ ] Virtual scrolling for queue
- [ ] Debounced search
- [ ] Optimistic UI updates
- [ ] Background refresh

## Known Limitations

1. **Sequential Upload**: Only one file uploads at a time (backend limitation)
2. **No Pause/Resume**: Once started, uploads can't be paused
3. **No Retry**: Failed uploads must be re-uploaded manually
4. **No Bulk Actions**: Can't delete multiple documents at once
5. **No Metadata**: Metadata field is placeholder (not yet wired)
6. **No PPTX**: PowerPoint support pending backend implementation

## Files Modified/Created

### Created
- `frontend/src/components/DocumentManagement.tsx` - Main component
- `frontend/src/services/documents.ts` - API service
- `DOCUMENT-MANAGEMENT-FEATURE.md` - This documentation

### Modified
- `frontend/src/components/AppShell.tsx` - Added navigation
- `frontend/src/types/index.ts` - Added document types
- `frontend/.env.example` - Added VITE_DOCUMENT_API_URL

## Dependencies

No new dependencies required! Uses existing:
- `@ui5/webcomponents-react` - UI components
- `@ui5/webcomponents-icons` - Icons
- Native `EventSource` API - SSE support
- Native `FormData` API - File uploads

## Troubleshooting

### Upload Not Starting
- Check backend is running on port 3001
- Verify `VITE_DOCUMENT_API_URL` in `.env`
- Check browser console for CORS errors

### Progress Not Updating
- Verify SSE endpoint accessible
- Check browser supports EventSource
- Look for network errors in console

### Documents Not Loading
- Verify backend `/api/documents` endpoint
- Check CORS configuration
- Ensure HANA DB connection working

### Delete Not Working
- Check document ID is correct
- Verify backend permissions
- Look for 404 errors (document not found)

---

**Ready to use!** Start both backends (chat on 8000, MCP on 3001) and navigate to Documents view to upload your first document. 🚀
