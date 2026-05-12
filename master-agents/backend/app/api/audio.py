"""Audio APIs for speech-to-text transcription."""
from __future__ import annotations

import logging
import mimetypes
from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from pydantic import BaseModel

from app.services.audio_transcription import transcribe_audio_bytes


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/audio", tags=["audio"])


class TranscriptionResponse(BaseModel):
    text: str


DEFAULT_PROMPT = "Transcribe this audio file. Provide the complete text content."


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    audio: UploadFile = File(...),
    prompt: str | None = Form(default=None),
    enable_timestamps: bool = Form(default=False),
):
    """Handle an audio transcription request."""
    try:
        contents = await audio.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Uploaded audio file is empty")

        mime_type = audio.content_type
        if not mime_type and audio.filename:
            mime_type, _ = mimetypes.guess_type(audio.filename)
        if not mime_type:
            logger.debug("Falling back to audio/mpeg MIME type for transcription")
            mime_type = "audio/mpeg"

        prompt_text = prompt or DEFAULT_PROMPT

        text = await transcribe_audio_bytes(
            audio_bytes=contents,
            mime_type=mime_type,
            prompt=prompt_text,
            enable_timestamps=enable_timestamps,
        )

        return TranscriptionResponse(text=text)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Audio transcription failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
