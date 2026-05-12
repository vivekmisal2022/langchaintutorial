/**
 * TypeScript type definitions for the Super Agent application.
 */

// ============================================================================
// User Types
// ============================================================================

export interface UserInfo {
  user_id: string;
  email: string;
  given_name: string;
  family_name: string;
  full_name: string;
  initials: string;
  avatar_url?: string;
}

// ============================================================================
// Chat Types
// ============================================================================

export interface ChatAttachment {
  id: string;
  name: string;
  type: string;
  size: number;
  previewUrl: string;
  file?: File;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  tables?: TableData[];
  attachments?: ChatAttachment[];
  timestamp: Date;
}

export interface ChatRequest {
  message: string;
  session_id?: string;
  timezone?: string;
}

export interface ChatSession {
  session_id: string;
  title: string;
  messages: ChatMessage[];
  created_at: Date;
  updated_at: Date;
}

export interface ChatHistoryItem {
  session_id: string;
  title: string;
  last_message: string;
  timestamp: Date;
  message_count: number;
}

export interface ChatHistoryItemApi {
  session_id: string;
  title: string;
  last_message: string;
  timestamp: string;
  message_count: number;
}

export interface ChatSessionApi {
  session_id: string;
  title: string;
  messages: ChatMessageApi[];
  created_at: string;
  updated_at: string;
}

export interface ChatAttachmentApi {
  id: string;
  name: string;
  mime_type: string;
  size: number;
  data: string;
}

export interface ChatMessageApi {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  tables?: TableData[];
  attachments?: ChatAttachmentApi[];
}

// ============================================================================
// Table Types
// ============================================================================

export interface TableColumn {
  header: string;
  accessor: string;
}

export interface TableData {
  columns: TableColumn[];
  rows: Record<string, any>[];
}

// ============================================================================
// SSE Event Types
// ============================================================================

export type SSEEventType = 'text' | 'table' | 'error' | 'end' | 'tool_start' | 'tool_end';

export interface SSETextEvent {
  type: 'text';
  content: string;
}

export interface SSETableEvent {
  type: 'table';
  data: TableData;
}

export interface SSEErrorEvent {
  type: 'error';
  message: string;
}

export interface SSEEndEvent {
  type: 'end';
}

export interface SSEToolStartEvent {
  type: 'tool_start';
  tool_name: string;
  tool_id: string;
  args?: Record<string, unknown>;
}

export interface SSEToolEndEvent {
  type: 'tool_end';
  tool_id: string;
  success: boolean;
}

export type SSEEvent = SSETextEvent | SSETableEvent | SSEErrorEvent | SSEEndEvent | SSEToolStartEvent | SSEToolEndEvent;

// ============================================================================
// Theme Types
// ============================================================================

export type ThemeMode = 'light' | 'dark' | 'system';

export interface ThemePreference {
  mode: ThemeMode;
}

// ============================================================================
// API Response Types
// ============================================================================

export interface ApiError {
  detail: string;
  status?: number;
}

export interface HealthResponse {
  status: string;
  mock_mode: boolean;
  cors_origins: string[];
}

// ============================================================================
// Document Management Types
// ============================================================================

export type JobStatus = 'queued' | 'running' | 'completed' | 'failed';
export type JobStage = 'queued' | 'parsing' | 'chunking' | 'embedding' | 'storing' | 'completed' | 'failed';

export interface UploadJob {
  job_id: string;
  filename: string;
  status: JobStatus;
  stage: JobStage;
  total_chunks: number;
  processed_chunks: number;
  created_at: string;
  updated_at?: string;
  completed_at?: string;
  error?: string;
  document_id?: string;
  message?: string;
}

export interface UploadResponse {
  success: boolean;
  message: string;
  jobs: UploadJob[];
}

export interface DocumentInfo {
  document_id: string;
  source_filename?: string;
  filename?: string;
  created_at?: string;
  last_ingested_at?: string;
  document_type?: string;
  total_chunks?: number;
  chunk_count?: number;
  total_pages?: number;
  tenant_id?: string;
  title?: string;
  summary?: string;
  score?: number;
}

export interface ListDocumentsResponse {
  success: boolean;
  documents: DocumentInfo[];
}

export interface DeleteDocumentResponse {
  success: boolean;
  document_id: string;
  chunks_deleted: number;
}

// Frontend-specific upload queue item
export interface QueuedUpload {
  id: string; // local ID for tracking
  file: File;
  job?: UploadJob; // populated after upload starts
  progress: number; // 0-100
  status: 'queued' | 'uploading' | 'processing' | 'completed' | 'failed';
  error?: string;
}
