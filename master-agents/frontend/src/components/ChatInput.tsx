/**
 * Chat input component with send button.
 */
import { useState, useRef, useEffect, useCallback } from 'react';
import { FlexBox, TextArea, Button, BusyIndicator, Text, MessageStrip } from '@ui5/webcomponents-react';
import type { TextAreaDomRef } from '@ui5/webcomponents-react';
import '@ui5/webcomponents-icons/dist/paper-plane.js';
import '@ui5/webcomponents-icons/dist/microphone.js';
import '@ui5/webcomponents-icons/dist/stop.js';
import '@ui5/webcomponents-icons/dist/image-viewer.js';
import '@ui5/webcomponents-icons/dist/sys-cancel.js';
import { useChat } from '../contexts/ChatContext';
import { streamChat } from '../services/api';
import type { SSEEvent } from '../types';
import { transcribeAudio } from '../services/audio';
import type { ChatAttachment } from '../types';

export function ChatInput() {
  const [input, setInput] = useState('');
  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);
  const [attachmentError, setAttachmentError] = useState<string | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [recordingError, setRecordingError] = useState<string | null>(null);
  const textAreaRef = useRef<TextAreaDomRef>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dropZoneRef = useRef<HTMLDivElement | null>(null);
  const [isDragActive, setIsDragActive] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const { addUserMessage, addResponseChunk, addToolStart, removeToolEnd, setStreaming, setError, finalizeResponse, isStreaming, activeSessionId } = useChat();

  // Auto-focus the input on mount, after sending a message, and when switching sessions
  useEffect(() => {
    if (!isStreaming && textAreaRef.current) {
      // Delay focus slightly to ensure scroll completes first
      const timer = setTimeout(() => {
        textAreaRef.current?.focus();
      }, 150);
      return () => clearTimeout(timer);
    }
  }, [isStreaming, activeSessionId]);

  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
      }
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  const resetAttachmentPreviews = useCallback((items: ChatAttachment[]) => {
    items.forEach((attachment) => {
      if (attachment.previewUrl.startsWith('blob:')) {
        URL.revokeObjectURL(attachment.previewUrl);
      }
    });
  }, []);

  useEffect(() => {
    return () => {
      resetAttachmentPreviews(attachments);
    };
  }, [attachments, resetAttachmentPreviews]);

  const handleSend = async () => {
    const message = input.trim();
    if ((message.length === 0 && attachments.length === 0) || isStreaming) return;

    // Clear input immediately for better UX
    const messageToSend = message;
    const attachmentsToSend = [...attachments];
    setInput('');
    setAttachments([]);
    setAttachmentError(null);
    setStreaming(true);
    setError(null);

    try {
      // IMPORTANT: Wait for user message to be saved before starting stream
      // This ensures attachments are persisted and available to the LLM
      await addUserMessage(messageToSend, attachmentsToSend);
      
      await streamChat(
        {
          message: messageToSend,
          session_id: activeSessionId || undefined,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
        },
        (event: SSEEvent) => {
          // Handle each SSE event
          if (event.type === 'text') {
            addResponseChunk({
              id: `${Date.now()}-${Math.random()}`,
              type: 'text',
              content: event.content,
              timestamp: new Date(),
            });
          } else if (event.type === 'table') {
            addResponseChunk({
              id: `${Date.now()}-${Math.random()}`,
              type: 'table',
              tableData: event.data,
              timestamp: new Date(),
            });
          } else if (event.type === 'tool_start') {
            addToolStart(event.tool_id, event.tool_name, event.args);
          } else if (event.type === 'tool_end') {
            removeToolEnd(event.tool_id);
          } else if (event.type === 'error') {
            setError(event.message);
          }
        },
        (error: Error) => {
          setError(`Connection error: ${error.message}`);
          setStreaming(false);
        },
        () => {
          finalizeResponse();
        }
      );
    } catch (error) {
      setError(`Failed to send message: ${error instanceof Error ? error.message : 'Unknown error'}`);
      setStreaming(false);
    }
  };

  const handleKeyDown = (e: CustomEvent) => {
    const nativeEvent = e as any;
    // Send on Enter (without Shift)
    if (nativeEvent.key === 'Enter' && !nativeEvent.shiftKey) {
      nativeEvent.preventDefault();
      handleSend();
    }
  };

  const handleAttachmentSelection = useCallback((files: FileList | File[]) => {
    const fileArray = Array.from(files);
    if (fileArray.length === 0) {
      return;
    }
    const validImages: ChatAttachment[] = [];
    let errorMessage: string | null = null;

    fileArray.forEach((file) => {
      if (!file.type.startsWith('image/')) {
        errorMessage = 'Only image attachments are currently supported.';
        return;
      }

      const previewUrl = URL.createObjectURL(file);
      validImages.push({
        id: `${file.name}-${file.lastModified}-${Math.random()}`,
        name: file.name,
        type: file.type,
        size: file.size,
        previewUrl,
        file,
      });
    });

    if (validImages.length > 0) {
      setAttachments((prev) => [...prev, ...validImages]);
    }

    if (errorMessage) {
      setAttachmentError(errorMessage);
    } else {
      setAttachmentError(null);
    }
  }, []);

  const handleFileInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files?.length) {
      handleAttachmentSelection(event.target.files);
      event.target.value = '';
    }
  };

  const handleAttachmentRemove = (attachmentId: string) => {
    setAttachments((prev) => {
      const attachment = prev.find((att) => att.id === attachmentId);
      if (attachment?.previewUrl.startsWith('blob:')) {
        URL.revokeObjectURL(attachment.previewUrl);
      }
      return prev.filter((att) => att.id !== attachmentId);
    });
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragActive(false);
    if (event.dataTransfer.files?.length) {
      handleAttachmentSelection(event.dataTransfer.files);
    }
  };

  const handleDragOver = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (!isDragActive) {
      setIsDragActive(true);
    }
  };

  const handleDragLeave = (event: React.DragEvent<HTMLDivElement>) => {
    if (dropZoneRef.current && !dropZoneRef.current.contains(event.relatedTarget as Node)) {
      setIsDragActive(false);
    }
  };

  const handlePaste = (event: React.ClipboardEvent<HTMLDivElement>) => {
    const files = event.clipboardData?.files;
    if (files && files.length > 0) {
      // Prevent default paste behavior to avoid file path being pasted as text
      event.preventDefault();
      handleAttachmentSelection(files);
    }
  };

  const resetMediaStream = () => {
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
    mediaRecorderRef.current = null;
  };

  const handleTranscription = async (blob: Blob) => {
    try {
      setIsTranscribing(true);
      const response = await transcribeAudio(blob);
      setInput((prev) => {
        const trimmedPrev = prev.trim();
        const trimmedTranscript = response.text.trim();
        if (!trimmedPrev) {
          return trimmedTranscript;
        }
        return `${trimmedPrev} ${trimmedTranscript}`.trim();
      });
      setRecordingError(null);
      setTimeout(() => {
        textAreaRef.current?.focus();
      }, 0);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to transcribe audio';
      setRecordingError(message);
      setError(message);
    } finally {
      setIsTranscribing(false);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
  };

  const startRecording = async () => {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      const message = 'Microphone access is not supported in this browser.';
      setRecordingError(message);
      setError(message);
      return;
    }

    try {
      setRecordingError(null);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaStreamRef.current = stream;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: mediaRecorder.mimeType || 'audio/webm' });
        audioChunksRef.current = [];
        resetMediaStream();
        if (audioBlob.size > 0) {
          await handleTranscription(audioBlob);
        }
      };

      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start();
      setIsRecording(true);
    } catch (error) {
      resetMediaStream();
      const message = error instanceof Error ? error.message : 'Unable to access microphone';
      setRecordingError(message);
      setError(message);
    }
  };

  const toggleRecording = () => {
    if (isRecording) {
      stopRecording();
    } else {
      void startRecording();
    }
  };

  return (
    <div
      ref={dropZoneRef}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onPaste={handlePaste}
      style={{
        borderTop: '1px solid var(--sapList_BorderColor)',
        backgroundColor: isDragActive ? 'var(--sapList_SelectionBackgroundColor)' : 'var(--sapBackgroundColor)',
        transition: 'background-color 0.2s ease',
      }}
    >
      <FlexBox
        direction="Column"
      >
      {(isRecording || isTranscribing) && (
        <FlexBox
          direction="Row"
          alignItems="Center"
          style={{ padding: '0.5rem 1rem 0 1rem', gap: '0.5rem' }}
        >
          <BusyIndicator active size="S" />
          <Text>{isRecording ? 'Recording… Press stop to transcribe.' : 'Transcribing audio…'}</Text>
        </FlexBox>
      )}
      {(recordingError || attachmentError) && (
        <MessageStrip
          design="Negative"
          hideCloseButton
          style={{ margin: '0.5rem 1rem 0 1rem' }}
        >
          {recordingError || attachmentError}
        </MessageStrip>
      )}
      {attachments.length > 0 && (
        <FlexBox
          direction="Row"
          wrap="Wrap"
          style={{ padding: '0.5rem 1rem 0 1rem', gap: '0.5rem' }}
        >
          {attachments.map((attachment) => (
            <div
              key={attachment.id}
              style={{
                position: 'relative',
                width: '5rem',
                height: '5rem',
                borderRadius: '0.5rem',
                overflow: 'hidden',
                border: '1px solid var(--sapList_BorderColor)',
              }}
            >
              <img
                src={attachment.previewUrl}
                alt={attachment.name}
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              />
              <Button
                icon="sys-cancel"
                design="Transparent"
                tooltip="Remove attachment"
                onClick={() => handleAttachmentRemove(attachment.id)}
                style={{
                  position: 'absolute',
                  top: '0.1rem',
                  right: '0.1rem',
                  minWidth: '1.5rem',
                  height: '1.5rem',
                  background: 'rgba(0,0,0,0.35)',
                }}
              />
            </div>
          ))}
        </FlexBox>
      )}
      <FlexBox
        direction="Row"
        alignItems="End"
        style={{
          padding: '1rem',
          gap: '0.5rem',
        }}
      >
        <TextArea
          ref={textAreaRef}
          value={input}
          onInput={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown as any}
          placeholder="Type your message… (Enter to send, Shift+Enter for new line)"
          rows={3}
          style={{ flex: 1 }}
          disabled={isStreaming || isTranscribing}
        />
        <FlexBox direction="Column" style={{ gap: '0.5rem' }}>
          <Button
            icon="image-viewer"
            design="Transparent"
            onClick={() => fileInputRef.current?.click()}
            tooltip="Attach images"
            disabled={isStreaming || isTranscribing}
          />
          <Button
            icon={isRecording ? 'stop' : 'microphone'}
            design={isRecording ? 'Negative' : 'Transparent'}
            onClick={toggleRecording}
            disabled={isStreaming || isTranscribing}
            tooltip={isRecording ? 'Stop recording' : 'Record audio message'}
          />
          <Button
            icon="paper-plane"
            design="Emphasized"
            onClick={handleSend}
            disabled={(input.trim().length === 0 && attachments.length === 0) || isStreaming || isRecording || isTranscribing}
            style={{ height: '2.75rem' }}
          >
            Send
          </Button>
        </FlexBox>
      </FlexBox>
      </FlexBox>
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        multiple
        style={{ display: 'none' }}
        onChange={handleFileInputChange}
      />
    </div>
  );
}
