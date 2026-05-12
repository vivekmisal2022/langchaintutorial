/**
 * Document management API service
 * Handles upload, list, delete, and progress tracking for documents
 */

import type {
  UploadResponse,
  ListDocumentsResponse,
  DeleteDocumentResponse,
  UploadJob,
} from '../types/index';

// Backend MCP server URL (different from main backend)
// Empty string uses relative paths through App Router in production
const DOCUMENT_API_BASE_URL = import.meta.env.VITE_DOCUMENT_API_URL || '';

/**
 * Upload one or more documents for ingestion
 * Backend processes one at a time, so frontend should queue multiple uploads
 */
export async function uploadDocument(file: File, tenantId?: string): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append('files', file);
  
  if (tenantId) {
    formData.append('tenant_id', tenantId);
  }

  const response = await fetch(`${DOCUMENT_API_BASE_URL}/api/documents/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(error || 'Failed to upload document');
  }

  return response.json();
}

/**
 * List all embedded documents
 */
export async function listDocuments(tenantId?: string): Promise<ListDocumentsResponse> {
  const params = new URLSearchParams();
  if (tenantId) {
    params.append('tenant_id', tenantId);
  }

  const url = `${DOCUMENT_API_BASE_URL}/api/documents${params.toString() ? `?${params.toString()}` : ''}`;
  const response = await fetch(url);

  if (!response.ok) {
    const error = await response.text();
    throw new Error(error || 'Failed to list documents');
  }

  return response.json();
}

/**
 * Delete a document and all its chunks
 */
export async function deleteDocument(documentId: string, tenantId?: string): Promise<DeleteDocumentResponse> {
  const params = new URLSearchParams();
  if (tenantId) {
    params.append('tenant_id', tenantId);
  }

  const url = `${DOCUMENT_API_BASE_URL}/api/documents/${documentId}${params.toString() ? `?${params.toString()}` : ''}`;
  const response = await fetch(url, {
    method: 'DELETE',
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(error || 'Failed to delete document');
  }

  return response.json();
}

/**
 * Get current job progress (polling)
 */
export async function getJobProgress(jobId: string): Promise<UploadJob> {
  const response = await fetch(`${DOCUMENT_API_BASE_URL}/api/documents/progress/${jobId}`);

  if (!response.ok) {
    const error = await response.text();
    throw new Error(error || 'Failed to get job progress');
  }

  const data = await response.json();
  return data.job;
}

/**
 * Stream job progress updates via Server-Sent Events
 * Returns an EventSource that emits progress updates
 */
export function streamJobProgress(
  jobId: string,
  onUpdate: (job: UploadJob) => void,
  onComplete: () => void,
  onError: (error: Error) => void
): EventSource {
  const eventSource = new EventSource(
    `${DOCUMENT_API_BASE_URL}/api/documents/progress/${jobId}/stream`
  );

  eventSource.onmessage = (event) => {
    try {
      const job: UploadJob = JSON.parse(event.data);
      onUpdate(job);

      if (job.status === 'completed' || job.status === 'failed') {
        eventSource.close();
        onComplete();
      }
    } catch (error) {
      console.error('Failed to parse SSE event:', error);
      onError(error instanceof Error ? error : new Error('Failed to parse SSE event'));
    }
  };

  eventSource.onerror = (error) => {
    console.error('SSE connection error:', error);
    eventSource.close();
    onError(new Error('Connection to progress stream failed'));
  };

  return eventSource;
}
