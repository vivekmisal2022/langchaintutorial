/**
 * Chat context for managing chat state and messages.
 */
import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import type { ChatMessage, TableData, ChatHistoryItem, ChatSession, ChatAttachment } from '../types';
import {
  fetchChatHistory,
  fetchChatSession,
  createChatSession as apiCreateChatSession,
  deleteChatSession as apiDeleteChatSession,
  appendChatMessage,
} from '../services/chatHistory';

export interface ChatContent {
  id: string;
  type: 'text' | 'table';
  content?: string;
  tableData?: TableData;
  timestamp: Date;
}

export interface ActiveTool {
  id: string;
  name: string;
  args?: Record<string, unknown>;
  startTime: Date;
}

interface ChatContextType {
  messages: ChatMessage[];
  sessions: ChatHistoryItem[];
  activeSessionId: string | null;
  currentResponse: ChatContent[];
  activeTools: ActiveTool[];
  isStreaming: boolean;
  error: string | null;
  addUserMessage: (content: string, attachments?: ChatAttachment[]) => void;
  addResponseChunk: (chunk: ChatContent) => void;
  addToolStart: (toolId: string, toolName: string, args?: Record<string, unknown>) => void;
  removeToolEnd: (toolId: string) => void;
  setStreaming: (streaming: boolean) => void;
  setError: (error: string | null) => void;
  finalizeResponse: () => void;
  clearChat: () => void;
  refreshSessions: () => Promise<void>;
  loadSession: (sessionId: string) => Promise<void>;
  createSession: () => Promise<void>;
  deleteSession: (sessionId: string) => Promise<void>;
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

/**
 * Convert a File object to base64 string (without data URL prefix)
 */
async function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      // Remove the data URL prefix (e.g., "data:image/jpeg;base64,")
      const base64 = result.split(',')[1];
      resolve(base64);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

export function ChatProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessions, setSessions] = useState<ChatHistoryItem[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [currentResponse, setCurrentResponse] = useState<ChatContent[]>([]);
  const [activeTools, setActiveTools] = useState<ActiveTool[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshSessions = useCallback(async () => {
    try {
      const data = await fetchChatHistory();
      setSessions(data);
      // Auto-load the most recent session on initial load
      if (!activeSessionId && data.length > 0) {
        const mostRecentSessionId = data[0].session_id;
        setActiveSessionId(mostRecentSessionId);
        // Load the session messages
        const session: ChatSession = await fetchChatSession(mostRecentSessionId);
        setMessages(session.messages);
      } else if (!activeSessionId && data.length === 0) {
        // No sessions exist - create a new one for first-time users
        console.log('No sessions found, creating initial session');
        const newSession = await apiCreateChatSession();
        setSessions([{
          session_id: newSession.session_id,
          title: newSession.title,
          last_message: '',
          timestamp: newSession.created_at,
          message_count: 0,
        }]);
        setActiveSessionId(newSession.session_id);
        setMessages([]);
      }
    } catch (err) {
      console.error('Failed to fetch chat history', err);
      setError('Failed to load chat history');
    }
  }, [activeSessionId]);

  useEffect(() => {
    void refreshSessions();
  }, [refreshSessions]);

  const loadSession = useCallback(async (sessionId: string) => {
    try {
      const session: ChatSession = await fetchChatSession(sessionId);
      setActiveSessionId(sessionId);
      setMessages(session.messages);
    } catch (err) {
      console.error('Failed to load chat session', err);
      setError('Failed to load chat session');
    }
  }, []);

  const createSession = useCallback(async () => {
    try {
      const session = await apiCreateChatSession();
      await refreshSessions();
      setActiveSessionId(session.session_id);
      setMessages([]);
    } catch (err) {
      console.error('Failed to create chat session', err);
      setError('Failed to create chat session');
    }
  }, [refreshSessions]);

  const deleteSession = useCallback(async (sessionId: string) => {
    try {
      const result = await apiDeleteChatSession(sessionId);
      await refreshSessions();
      
      if (activeSessionId === sessionId) {
        // If a new session was auto-created (last session deleted), use it
        if (result.new_session_id) {
          setActiveSessionId(result.new_session_id);
          const session = await fetchChatSession(result.new_session_id);
          setMessages(session.messages);
        } else {
          // Otherwise, load the most recent remaining session
          const updated = await fetchChatHistory();
          if (updated.length > 0) {
            const newSessionId = updated[0].session_id;
            setActiveSessionId(newSessionId);
            const session = await fetchChatSession(newSessionId);
            setMessages(session.messages);
          } else {
            // Shouldn't happen since backend creates new session, but handle it
            setActiveSessionId(null);
            setMessages([]);
          }
        }
      }
    } catch (err) {
      console.error('Failed to delete session', err);
      setError('Failed to delete session');
    }
  }, [activeSessionId, refreshSessions]);

  const addUserMessage = async (content: string, attachments: ChatAttachment[] = []) => {
    const message: ChatMessage = {
      role: 'user',
      content,
      ...(attachments.length > 0 && { attachments }),
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, message]);
    setCurrentResponse([]);
    setError(null);

    if (activeSessionId) {
      // Convert File objects to base64 for backend persistence
      const attachmentsForBackend = await Promise.all(
        attachments.map(async (att) => {
          if (att.file) {
            // Convert File to base64
            const base64Data = await fileToBase64(att.file);
            return {
              id: att.id,
              name: att.name,
              mime_type: att.type,
              size: att.size,
              data: base64Data,
            };
          }
          return null;
        })
      );

      const validAttachments = attachmentsForBackend.filter((att): att is NonNullable<typeof att> => att !== null);

      // IMPORTANT: Wait for message to be saved before returning
      // This ensures the message is persisted before the chat stream starts
      await appendChatMessage(activeSessionId, {
        role: 'user',
        content,
        timestamp: message.timestamp,
        ...(validAttachments.length > 0 && { attachments: validAttachments }),
      });
      
      await refreshSessions();
    }
  };

  const addResponseChunk = (chunk: ChatContent) => {
    setCurrentResponse(prev => [...prev, chunk]);
  };

  const addToolStart = (toolId: string, toolName: string, args?: Record<string, unknown>) => {
    setActiveTools(prev => [...prev, { id: toolId, name: toolName, args, startTime: new Date() }]);
  };

  const removeToolEnd = (toolId: string) => {
    setActiveTools(prev => prev.filter(t => t.id !== toolId));
  };

  const setStreaming = (streaming: boolean) => {
    setIsStreaming(streaming);
    // Clear active tools when streaming stops
    if (!streaming) {
      setActiveTools([]);
    }
  };

  const finalizeResponse = () => {
    setIsStreaming(false);
    
    // Use functional update to capture current value
    setCurrentResponse(prev => {
      const rawText = prev
        .filter(c => c.type === 'text')
        .map(c => c.content)
        .join('');

      const textContent = rawText.replace(/\s+$/, '');

      const tables = prev
        .filter(c => c.type === 'table' && c.tableData)
        .map(c => c.tableData!);

      // Add finalized message if we have content or tables
      if (rawText.trim() || tables.length > 0) {
        const message: ChatMessage = {
          role: 'assistant',
          content: textContent || 'Table data',
          ...(tables.length > 0 && { tables }),
          timestamp: new Date(),
        };
        
        setMessages(msgs => [...msgs, message]);

        if (activeSessionId) {
          void appendChatMessage(activeSessionId, {
            role: 'assistant',
            content: message.content,
            tables,
            timestamp: message.timestamp,
          }).then(async (updatedSession) => {
            setMessages(updatedSession.messages);
            await refreshSessions();
          }).catch((err) => {
            console.error('Failed to persist assistant message', err);
          });
        }
      }
      
      // Clear currentResponse
      return [];
    });
  };

  const clearChat = () => {
    setMessages([]);
    setCurrentResponse([]);
    setActiveTools([]);
    setIsStreaming(false);
    setError(null);
  };

  return (
    <ChatContext.Provider
      value={{
        messages,
        currentResponse,
        activeTools,
        isStreaming,
        error,
        sessions,
        activeSessionId,
        addUserMessage,
        addResponseChunk,
        addToolStart,
        removeToolEnd,
        setStreaming,
        setError,
        finalizeResponse,
        clearChat,
        refreshSessions,
        loadSession,
        createSession,
        deleteSession,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
}

export function useChat() {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChat must be used within ChatProvider');
  }
  return context;
}
