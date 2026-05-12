import { API_BASE_URL } from './api';

export interface TranscriptionOptions {
  prompt?: string;
  enableTimestamps?: boolean;
}

export interface TranscriptionResponse {
  text: string;
}

export async function transcribeAudio(
  audioBlob: Blob,
  options: TranscriptionOptions = {}
): Promise<TranscriptionResponse> {
  const formData = new FormData();
  formData.append('audio', audioBlob, options.prompt ? 'recording_with_prompt.webm' : 'recording.webm');
  if (options.prompt) {
    formData.append('prompt', options.prompt);
  }
  if (options.enableTimestamps) {
    formData.append('enable_timestamps', String(options.enableTimestamps));
  }

  const response = await fetch(`${API_BASE_URL}/api/audio/transcribe`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || 'Failed to transcribe audio');
  }

  return response.json();
}
