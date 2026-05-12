import type {
  ChatHistoryItem,
  ChatSession,
  ChatHistoryItemApi,
  ChatSessionApi,
  TableData,
  ChatAttachmentApi,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? '';

/**
 * Parse a timestamp string from the backend as UTC.
 *
 * Python's datetime.now() produces ISO strings without a timezone suffix
 * (e.g. "2026-03-22T21:34:29.123456"). JavaScript's `new Date()` treats
 * these as local time, which causes wrong relative-time calculations
 * when the browser is not in UTC. We append "Z" to force UTC parsing.
 */
function parseUtcTimestamp(ts: string): Date {
  // If the string already has a timezone indicator (Z, +, or - offset), leave it alone
  if (/[Zz]$/.test(ts) || /[+-]\d{2}:\d{2}$/.test(ts)) {
    return new Date(ts);
  }
  return new Date(ts + 'Z');
}

/**
 * Convert API attachment format to frontend format
 */
function convertApiAttachment(apiAtt: ChatAttachmentApi) {
  return {
    id: apiAtt.id,
    name: apiAtt.name,
    type: apiAtt.mime_type,
    size: apiAtt.size,
    previewUrl: `data:${apiAtt.mime_type};base64,${apiAtt.data}`,
  };
}

export async function fetchChatHistory(): Promise<ChatHistoryItem[]> {
  const response = await fetch(`${API_BASE_URL}/api/chat-history`);
  if (!response.ok) {
    throw new Error('Failed to fetch chat history');
  }
  const data: ChatHistoryItemApi[] = await response.json();
  return data.map((item) => ({
    ...item,
    timestamp: parseUtcTimestamp(item.timestamp),
  }));
}

export async function fetchChatSession(sessionId: string): Promise<ChatSession> {
  const response = await fetch(`${API_BASE_URL}/api/chat-history/${sessionId}`);
  if (!response.ok) {
    throw new Error('Failed to fetch chat session');
  }
  const data: ChatSessionApi = await response.json();
  return {
    ...data,
    created_at: parseUtcTimestamp(data.created_at),
    updated_at: parseUtcTimestamp(data.updated_at),
    messages: data.messages.map((message) => ({
      role: message.role,
      content: message.content,
      timestamp: parseUtcTimestamp(message.timestamp),
      tables: message.tables,
      attachments: message.attachments?.map(convertApiAttachment),
    })),
  };
}

export async function createChatSession(title: string = 'New Chat'): Promise<ChatSession> {
  const response = await fetch(`${API_BASE_URL}/api/chat-history`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
  if (!response.ok) {
    throw new Error('Failed to create chat session');
  }
  const data: ChatSessionApi = await response.json();
  return {
    ...data,
    created_at: parseUtcTimestamp(data.created_at),
    updated_at: parseUtcTimestamp(data.updated_at),
    messages: data.messages.map((message) => ({
      role: message.role,
      content: message.content,
      timestamp: parseUtcTimestamp(message.timestamp),
      tables: message.tables,
      attachments: message.attachments?.map(convertApiAttachment),
    })),
  };
}

export async function deleteChatSession(sessionId: string): Promise<{ success: boolean; session_id: string; new_session_id?: string }> {
  const response = await fetch(`${API_BASE_URL}/api/chat-history/${sessionId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error('Failed to delete chat session');
  }
  return response.json();
}

interface AppendMessagePayload {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  tables?: TableData[];
  attachments?: ChatAttachmentApi[];
}

export async function appendChatMessage(
  sessionId: string,
  payload: AppendMessagePayload,
): Promise<ChatSession> {
  const response = await fetch(`${API_BASE_URL}/api/chat-history/${sessionId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      role: payload.role,
      content: payload.content,
      timestamp: payload.timestamp.toISOString(),
      tables: payload.tables,
      attachments: payload.attachments,
    }),
  });

  if (!response.ok) {
    throw new Error('Failed to append chat message');
  }

  const data: ChatSessionApi = await response.json();
  return {
    ...data,
    created_at: parseUtcTimestamp(data.created_at),
    updated_at: parseUtcTimestamp(data.updated_at),
    messages: data.messages.map((message) => ({
      role: message.role,
      content: message.content,
      timestamp: parseUtcTimestamp(message.timestamp),
      tables: message.tables,
      attachments: message.attachments?.map(convertApiAttachment),
    })),
  };
}
