/**
 * API service for communicating with the backend.
 */
import type { ChatRequest, SSEEvent, HealthResponse } from '../types';

export const API_BASE_URL = import.meta.env.VITE_API_URL || '';

/**
 * Check backend health status.
 */
export async function checkHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`);
  
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Stream chat responses using Server-Sent Events (SSE).
 * 
 * @param request - Chat request with message and optional session_id
 * @param onEvent - Callback for each SSE event
 * @param onError - Callback for errors
 * @param onComplete - Callback when stream completes
 */
export async function streamChat(
  request: ChatRequest,
  onEvent: (event: SSEEvent) => void,
  onError: (error: Error) => void,
  onComplete: () => void
): Promise<void> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/chat-stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    if (!response.body) {
      throw new Error('Response body is null');
    }

    // Read the stream
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      
      if (done) {
        break;
      }

      // Decode the chunk and add to buffer
      buffer += decoder.decode(value, { stream: true });

      // Process complete SSE messages
      // Split by double newline to get complete events (SSE spec)
      const events = buffer.split('\n\n');
      buffer = events.pop() || ''; // Keep incomplete event in buffer

      for (const eventBlock of events) {
        if (!eventBlock.trim()) continue;

        let currentEvent: string | null = null;
        const dataLines: string[] = [];

        // Parse each line in the event block
        const lines = eventBlock.split('\n');
        for (const line of lines) {
          if (line.startsWith('event:')) {
            currentEvent = line.substring(6).trim();
          } else if (line.startsWith('data:')) {
            // Remove 'data:' prefix and the single space after it (SSE spec)
            // Multiple data lines are joined with newlines
            dataLines.push(line.substring(6));
          }
        }

        // Process the complete event
        if (currentEvent && dataLines.length > 0) {
          try {
            const currentData = dataLines.join('\n');
            const event = parseSSEEvent(currentEvent, currentData);
            onEvent(event);
            
            // Check if this is the end event
            if (event.type === 'end') {
              onComplete();
              return;
            }
          } catch (error) {
            console.error('Error parsing SSE event:', error);
          }
        }
      }
    }

    onComplete();
  } catch (error) {
    onError(error instanceof Error ? error : new Error(String(error)));
  }
}

/**
 * Parse SSE event based on type.
 */
function parseSSEEvent(eventType: string, data: string): SSEEvent {
  switch (eventType) {
    case 'text':
      return {
        type: 'text',
        content: data,
      };

    case 'table':
      return {
        type: 'table',
        data: JSON.parse(data),
      };

    case 'error':
      return {
        type: 'error',
        message: data,
      };

    case 'end':
      return {
        type: 'end',
      };

    case 'tool_start': {
      const parsed = JSON.parse(data);
      return {
        type: 'tool_start',
        tool_name: parsed.tool_name,
        tool_id: parsed.tool_id,
        args: parsed.args,
      };
    }

    case 'tool_end': {
      const parsed = JSON.parse(data);
      return {
        type: 'tool_end',
        tool_id: parsed.tool_id,
        success: parsed.success,
      };
    }

    default:
      throw new Error(`Unknown event type: ${eventType}`);
  }
}
