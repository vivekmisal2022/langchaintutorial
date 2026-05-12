/**
 * Document Management page
 * Allows users to upload, view, and delete documents for RAG
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import {
  FlexBox,
  Title,
  Text,
  Button,
  Input,
  Table,
  TableHeaderRow,
  TableHeaderCell,
  TableRow,
  TableCell,
  ProgressIndicator,
  MessageStrip,
  Label,
  Toast,
  Icon,
  Dialog,
  ObjectStatus,
} from '@ui5/webcomponents-react';
import type { InputPropTypes } from '@ui5/webcomponents-react';
import '@ui5/webcomponents-icons/dist/upload.js';
import '@ui5/webcomponents-icons/dist/delete.js';
import '@ui5/webcomponents-icons/dist/search.js';
import '@ui5/webcomponents-icons/dist/document.js';
import type { DocumentInfo, QueuedUpload, UploadJob, JobStage, JobStatus } from '../types/index';
import {
  uploadDocument,
  listDocuments,
  deleteDocument,
  streamJobProgress,
} from '../services/documents';

const normalizeJob = (job: UploadJob): UploadJob => {
  const stage = (job.stage || 'queued') as JobStage;
  const status = (job.status || 'running') as JobStatus;
  return {
    ...job,
    stage,
    status,
    total_chunks: job.total_chunks ?? (job as any).totalChunks ?? 0,
    processed_chunks: job.processed_chunks ?? (job as any).processedChunks ?? 0,
    created_at: job.created_at ?? (job as any).createdAt ?? new Date().toISOString(),
    updated_at: job.updated_at ?? (job as any).updatedAt,
    completed_at: job.completed_at ?? (job as any).completedAt,
    document_id: job.document_id ?? (job as any).documentId,
    message: job.message ?? (job as any).message,
  };
};

const clampProgressValue = (value: number): number =>
  Math.min(100, Math.max(0, Math.round(value)));

export function DocumentManagement() {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [uploadQueue, setUploadQueue] = useState<QueuedUpload[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toastOpen, setToastOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState('');
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<DocumentInfo | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const processingRef = useRef(false);
  const handleSearchInput = useCallback<NonNullable<InputPropTypes['onInput']>>((event) => {
    setSearchQuery(event.target.value ?? '');
  }, []);

  // Load documents on mount
  useEffect(() => {
    loadDocuments();
  }, []);

  // Process upload queue
  useEffect(() => {
    processQueue();
  }, [uploadQueue]);

  const loadDocuments = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await listDocuments();
      setDocuments(response.documents);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load documents');
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    // Add files to queue
    const newUploads: QueuedUpload[] = Array.from(files).map((file) => ({
      id: `${Date.now()}-${Math.random()}`,
      file,
      progress: 0,
      status: 'queued',
    }));

    setUploadQueue((prev) => [...prev, ...newUploads]);

    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const processQueue = async () => {
    // Prevent concurrent processing
    if (processingRef.current) return;

    // Find next queued item
    const nextUpload = uploadQueue.find((u) => u.status === 'queued');
    if (!nextUpload) {
      processingRef.current = false;
      return;
    }

    processingRef.current = true;

    try {
      // Update status to uploading
      setUploadQueue((prev) =>
        prev.map((u) =>
          u.id === nextUpload.id ? { ...u, status: 'uploading', progress: 10 } : u
        )
      );

      // Upload file
      const response = await uploadDocument(nextUpload.file);
      const job = response.jobs[0] ? normalizeJob(response.jobs[0]) : undefined;

      if (!job) {
        throw new Error('No job returned from upload');
      }

      // Update with job info
      setUploadQueue((prev) =>
        prev.map((u) =>
          u.id === nextUpload.id
            ? { ...u, job, status: 'processing', progress: 20 }
            : u
        )
      );

      // Stream progress updates
      streamJobProgress(
        job.job_id,
        (incomingJob) => {
          const updatedJob = normalizeJob(incomingJob as UploadJob);
          setUploadQueue((prev) =>
            prev.map((u) => {
              if (u.id !== nextUpload.id) return u;

              // Calculate progress based on stage
              let progress = 20;
              if (updatedJob.stage === 'parsing') progress = 30;
              else if (updatedJob.stage === 'chunking') progress = 40;
              else if (updatedJob.stage === 'embedding') {
                const embeddingProgress =
                  updatedJob.total_chunks > 0
                    ? (updatedJob.processed_chunks / updatedJob.total_chunks) * 40
                    : 0;
                progress = 40 + embeddingProgress;
              } else if (updatedJob.stage === 'storing') progress = 90;
              else if (updatedJob.stage === 'completed') progress = 100;

              const normalizedProgress = clampProgressValue(progress);

              return {
                ...u,
                job: updatedJob,
                progress: normalizedProgress,
                status:
                  updatedJob.status === 'completed'
                    ? 'completed'
                    : updatedJob.status === 'failed'
                    ? 'failed'
                    : 'processing',
                error: updatedJob.error,
              };
            })
          );
        },
        () => {
          // On complete, reload documents and remove from queue
          loadDocuments();
          setUploadQueue((prev) => prev.filter((u) => u.id !== nextUpload.id));
          processingRef.current = false;
        },
        (err) => {
          setUploadQueue((prev) =>
            prev.map((u) =>
              u.id === nextUpload.id
                ? { ...u, status: 'failed', error: err.message }
                : u
            )
          );
          processingRef.current = false;
        }
      );
    } catch (err) {
      setUploadQueue((prev) =>
        prev.map((u) =>
          u.id === nextUpload.id
            ? {
                ...u,
                status: 'failed',
                error: err instanceof Error ? err.message : 'Upload failed',
              }
            : u
        )
      );
      processingRef.current = false;
    }
  };

  const openDeleteDialog = (doc: DocumentInfo) => {
    setPendingDelete(doc);
    setDeleteDialogOpen(true);
  };

  const closeDeleteDialog = () => {
    setDeleteDialogOpen(false);
    setPendingDelete(null);
    setIsDeleting(false);
  };

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    try {
      setIsDeleting(true);
      await deleteDocument(pendingDelete.document_id);
      setToastMessage('Document deleted successfully');
      setToastOpen(true);
      closeDeleteDialog();
      loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete document');
      setIsDeleting(false);
    }
  };

  const getDocumentName = (doc: DocumentInfo) =>
    doc.source_filename || doc.filename || 'Untitled Document';

  const getDocumentTitle = (doc: DocumentInfo) =>
    (doc.title && doc.title.trim().length > 0 ? doc.title : undefined) || getDocumentName(doc);

  const getUploadDate = (doc: DocumentInfo) => doc.created_at || doc.last_ingested_at || '';

  const getChunkCount = (doc: DocumentInfo) => doc.total_chunks ?? doc.chunk_count ?? 0;

  const getSummarySnippet = (doc: DocumentInfo, maxLength: number = 220) => {
    if (!doc.summary) return '';
    const normalized = doc.summary.replace(/\s+/g, ' ').trim();
    if (normalized.length <= maxLength) return normalized;
    return `${normalized.slice(0, maxLength - 1)}…`;
  };

  const getDocumentTypeLabel = (doc: DocumentInfo) => {
    const raw = doc.document_type || '';
    if (!raw) return 'Unknown';
    const normalized = raw.toLowerCase();

    if (normalized.includes('pdf')) return 'PDF';
    if (normalized.includes('word')) return 'Word';
    if (normalized.includes('excel')) return 'Excel';
    if (normalized.includes('powerpoint')) return 'PowerPoint';
    if (normalized.includes('markdown') || normalized.includes('md')) return 'Markdown';
    if (normalized.includes('text') || normalized.includes('txt')) return 'Text';

    return raw.replace(/_/g, ' ');
  };

  const filteredDocuments = documents.filter((doc) => {
    const query = searchQuery.toLowerCase();
    if (!query) return true;

    const title = getDocumentTitle(doc).toLowerCase();
    const filename = getDocumentName(doc).toLowerCase();
    const summary = (doc.summary || '').toLowerCase();

    return (
      title.includes(query) ||
      filename.includes(query) ||
      summary.includes(query)
    );
  });

  return (
    <FlexBox
      direction="Column"
      style={{
        flex: 1,
        padding: '2rem',
        gap: '1.5rem',
        overflow: 'auto',
        backgroundColor: 'var(--sapBackgroundColor)',
      }}
    >
      {/* Header */}
      <FlexBox justifyContent="SpaceBetween" alignItems="Start" style={{ gap: '1rem' }}>
        <FlexBox direction="Column" style={{ gap: '0.5rem', minWidth: '18rem' }}>
          <Title level="H1">Manage Your Documents</Title>
          <Text style={{ color: 'var(--sapContent_LabelColor)' }}>
            Upload, search, and manage documents for AI analysis.
          </Text>
        </FlexBox>
        <Button
          icon="upload"
          design="Emphasized"
          onClick={() => fileInputRef.current?.click()}
        >
          Upload Document
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.docx,.md,.txt,.doc"
          style={{ display: 'none' }}
          onChange={handleFileSelect}
        />
      </FlexBox>

      {/* Error Message */}
      {error && (
        <MessageStrip
          design="Negative"
          onClose={() => setError(null)}
        >
          {error}
        </MessageStrip>
      )}

      {/* Upload Queue */}
      {uploadQueue.length > 0 && (
        <FlexBox
          direction="Column"
          style={{
            gap: '1rem',
            padding: '1rem',
            backgroundColor: 'var(--sapGroup_ContentBackground)',
            borderRadius: '0.5rem',
            border: '1px solid var(--sapGroup_BorderColor)',
          }}
        >
          <Label>Upload Queue ({uploadQueue.length})</Label>
          {uploadQueue.map((upload) => (
            <FlexBox
              key={upload.id}
              direction="Column"
              style={{ gap: '0.5rem' }}
            >
              <FlexBox justifyContent="SpaceBetween" alignItems="Center">
                <Text style={{ fontWeight: 'bold' }}>{upload.file.name}</Text>
                <Text
                  style={{
                    fontSize: '0.875rem',
                    color: 'var(--sapContent_LabelColor)',
                  }}
                >
                  {upload.status === 'queued' && 'Queued'}
                  {upload.status === 'uploading' && 'Uploading...'}
                  {upload.status === 'processing' &&
                    (upload.job?.stage || 'Processing...')}
                  {upload.status === 'completed' && '✓ Completed'}
                  {upload.status === 'failed' && '✗ Failed'}
                </Text>
              </FlexBox>
              <ProgressIndicator
                value={clampProgressValue(upload.progress)}
                displayValue={`${clampProgressValue(upload.progress)}%`}
                valueState={
                  upload.status === 'failed'
                    ? 'Negative'
                    : upload.status === 'completed'
                    ? 'Positive'
                    : 'Information'
                }
              />
              {upload.error && (
                <Text style={{ color: 'var(--sapNegativeColor)', fontSize: '0.875rem' }}>
                  {upload.error}
                </Text>
              )}
              {upload.job?.message && (
                <Text style={{ fontSize: '0.875rem', color: 'var(--sapContent_LabelColor)' }}>
                  {upload.job.message}
                </Text>
              )}
            </FlexBox>
          ))}
        </FlexBox>
      )}

      {/* Search */}
      <FlexBox
        style={{
          padding: '0.75rem 1rem',
          backgroundColor: 'var(--sapGroup_ContentBackground)',
          borderRadius: '0.5rem',
          border: '1px solid var(--sapGroup_BorderColor)',
        }}
      >
        <Input
          icon={<Icon name="search" />}
          placeholder="Search documents by name..."
          value={searchQuery}
          onInput={handleSearchInput}
          style={{ width: '100%' }}
        />
      </FlexBox>

      {/* Documents Table */}
      {filteredDocuments.length === 0 && !loading ? (
        <FlexBox
          direction="Column"
          alignItems="Center"
          justifyContent="Center"
          style={{
            flex: 1,
            gap: '1.5rem',
            padding: '3rem',
            border: '2px dashed var(--sapGroup_BorderColor)',
            borderRadius: '0.5rem',
          }}
        >
          <Icon name="document" style={{ fontSize: '3rem', color: 'var(--sapContent_IconColor)' }} />
          <FlexBox direction="Column" alignItems="Center" style={{ gap: '0.5rem' }}>
            <Title level="H3">No documents uploaded yet</Title>
            <Text style={{ color: 'var(--sapContent_LabelColor)' }}>
              Get started by uploading your first document for AI analysis.
            </Text>
          </FlexBox>
          <Button
            icon="upload"
            design="Emphasized"
            onClick={() => fileInputRef.current?.click()}
          >
            Upload Document
          </Button>
        </FlexBox>
      ) : (
        <Table
          headerRow={
            <TableHeaderRow>
              <TableHeaderCell width="30%">
                <Label>Title & File</Label>
              </TableHeaderCell>
              <TableHeaderCell width="44%">
                <Label>Summary</Label>
              </TableHeaderCell>
              <TableHeaderCell width="6rem" style={{ textAlign: 'center' }}>
                <Label>Pages</Label>
              </TableHeaderCell>
              <TableHeaderCell width="6rem" style={{ textAlign: 'center' }}>
                <Label>Chunks</Label>
              </TableHeaderCell>
              <TableHeaderCell width="11rem">
                <Label>Created</Label>
              </TableHeaderCell>
              <TableHeaderCell width="4rem" style={{ textAlign: 'center', minWidth: '3.5rem' }}>
                <Label>Actions</Label>
              </TableHeaderCell>
            </TableHeaderRow>
          }
          style={{
            border: '1px solid var(--sapList_BorderColor)',
            borderRadius: '0.5rem',
            overflow: 'hidden',
          }}
        >
          {filteredDocuments.map((doc) => (
            <TableRow key={doc.document_id}>
              <TableCell>
                <FlexBox direction="Column" style={{ gap: '0.25rem' }}>
                  <Text style={{ fontWeight: 'bold' }}>{getDocumentTitle(doc)}</Text>
                  <Text
                    style={{
                      fontSize: '0.75rem',
                      color: 'var(--sapContent_LabelColor)',
                    }}
                  >
                    {getDocumentName(doc)}
                  </Text>
                  <ObjectStatus
                    state="Information"
                    style={{
                      fontSize: '0.75rem',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.25rem',
                    }}
                  >
                    <Icon name="document" style={{ fontSize: '0.75rem' }} />
                    {getDocumentTypeLabel(doc)}
                  </ObjectStatus>
                </FlexBox>
              </TableCell>
              <TableCell>
                {doc.summary ? (
                  <Text
                    style={{
                      color: 'var(--sapContent_LabelColor)',
                      fontSize: '0.875rem',
                    }}
                    title={doc.summary}
                  >
                    {getSummarySnippet(doc)}
                  </Text>
                ) : (
                  <Text
                    style={{
                      color: 'var(--sapContent_LabelColor)',
                      fontSize: '0.875rem',
                      fontStyle: 'italic',
                    }}
                  >
                    No summary available
                  </Text>
                )}
              </TableCell>
              <TableCell>
                <Text style={{ color: 'var(--sapContent_LabelColor)' }}>
                  {doc.total_pages ?? '—'}
                </Text>
              </TableCell>
              <TableCell>
                <Text style={{ color: 'var(--sapContent_LabelColor)' }}>
                  {getChunkCount(doc)}
                </Text>
              </TableCell>
              <TableCell>
                <Text style={{ color: 'var(--sapContent_LabelColor)' }}>
                  {(() => {
                    const dateValue = getUploadDate(doc);
                    if (!dateValue) {
                      return 'Unknown';
                    }
                    const parsed = new Date(dateValue);
                    return isNaN(parsed.getTime())
                      ? 'Unknown'
                      : parsed.toLocaleString(undefined, {
                          year: 'numeric',
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        });
                  })()}
                </Text>
              </TableCell>
              <TableCell>
                <Button
                  icon="delete"
                  design="Transparent"
                  onClick={() => openDeleteDialog(doc)}
                  tooltip="Delete document"
                />
              </TableCell>
            </TableRow>
          ))}
        </Table>
      )}

      {/* Toast */}
      <Toast open={toastOpen} onClose={() => setToastOpen(false)}>
        {toastMessage}
      </Toast>

      {/* Delete confirmation dialog */}
      <Dialog
        open={deleteDialogOpen}
        headerText="Delete document"
        accessibleName="Delete document confirmation"
        onClose={closeDeleteDialog}
      >
        <Text>
          Are you sure you want to delete{' '}
          <strong>{pendingDelete ? getDocumentName(pendingDelete) : 'this document'}</strong>?
        </Text>
        <FlexBox
          slot="footer"
          justifyContent="End"
          style={{ gap: '0.5rem', width: '100%' }}
        >
          <Button design="Transparent" onClick={closeDeleteDialog} disabled={isDeleting}>
            Cancel
          </Button>
          <Button design="Negative" onClick={confirmDelete} disabled={isDeleting}>
            Delete
          </Button>
        </FlexBox>
      </Dialog>
    </FlexBox>
  );
}
