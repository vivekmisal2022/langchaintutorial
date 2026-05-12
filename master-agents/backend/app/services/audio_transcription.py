"""Audio transcription service using SAP Generative AI Hub (Gemini 2.5 Flash)."""
from __future__ import annotations

import asyncio
import base64
import logging
from typing import Optional, Any

from gen_ai_hub.proxy.native.google_genai.clients import Client, get_proxy_client

from app.core.config import settings

logger = logging.getLogger(__name__)

_audio_client: Optional[Client] = None


def _resolve_audio_profile() -> tuple[dict[str, str], str]:
    """Return the AI Core profile to use for audio transcription."""

    instance = (settings.audio_model_instance or "US").strip().upper()
    if instance not in {"US", "JP"}:
        raise ValueError(
            "Unsupported AUDIO_MODEL_INSTANCE value. Use 'US' or 'JP'."
        )

    if instance == "US":
        profile = {
            "base_url": settings.aicore_base_url_us,
            "auth_url": settings.aicore_auth_url_us,
            "client_id": settings.aicore_client_id_us,
            "client_secret": settings.aicore_client_secret_us,
            "resource_group": settings.aicore_resource_group_us,
        }
        required_names = [
            ("AICORE_BASE_URL_US", profile["base_url"]),
            ("AICORE_AUTH_URL_US", profile["auth_url"]),
            ("AICORE_CLIENT_ID_US", profile["client_id"]),
            ("AICORE_CLIENT_SECRET_US", profile["client_secret"]),
            ("AICORE_RESOURCE_GROUP_US", profile["resource_group"]),
        ]
    else:  # JP
        profile = {
            "base_url": settings.aicore_base_url,
            "auth_url": settings.aicore_auth_url,
            "client_id": settings.aicore_client_id,
            "client_secret": settings.aicore_client_secret,
            "resource_group": settings.aicore_resource_group,
        }
        required_names = [
            ("AICORE_BASE_URL", profile["base_url"]),
            ("AICORE_AUTH_URL", profile["auth_url"]),
            ("AICORE_CLIENT_ID", profile["client_id"]),
            ("AICORE_CLIENT_SECRET", profile["client_secret"]),
            ("AICORE_RESOURCE_GROUP", profile["resource_group"]),
        ]

    missing = [name for name, value in required_names if not value]
    if missing:
        raise ValueError(
            "Missing required AI Core configuration values for"
            f" {instance} instance: " + ", ".join(missing)
        )

    return profile, instance


def _get_audio_client() -> Client:
    """Return a singleton Client configured for the selected instance."""
    global _audio_client

    if _audio_client is not None:
        return _audio_client

    profile, instance = _resolve_audio_profile()

    logger.info(
        "Initializing audio transcription client (%s region)", instance
    )

    # Create proxy client with credentials
    proxy_client = get_proxy_client(
        proxy_version="gen-ai-hub",
        base_url=profile["base_url"],
        auth_url=profile["auth_url"],
        client_id=profile["client_id"],
        client_secret=profile["client_secret"],
        resource_group=profile["resource_group"],
    )

    # Create the Google GenAI Client with proxy
    _audio_client = Client(proxy_client=proxy_client)
    return _audio_client


async def transcribe_audio_bytes(
    audio_bytes: bytes,
    mime_type: str,
    prompt: str,
    enable_timestamps: bool = False,
) -> str:
    """Transcribe raw audio bytes and return the generated text."""

    if not audio_bytes:
        raise ValueError("Audio payload is empty")

    client = _get_audio_client()
    base64_data = base64.b64encode(audio_bytes).decode("utf-8")

    # Build content with inline audio data
    contents = [
        {
            "role": "user",
            "parts": [
                {"text": prompt},
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": base64_data,
                    }
                },
            ],
        }
    ]

    generation_config = {"audio_timestamp": True} if enable_timestamps else None

    loop = asyncio.get_running_loop()
    logger.debug(
        "Submitting audio transcription request (mime=%s, timestamps=%s)",
        mime_type,
        enable_timestamps,
    )

    def _invoke_model():
        return client.models.generate_content(
            model=settings.audio_transcription_model,
            contents=contents,
            config=generation_config,
        )

    response = await loop.run_in_executor(None, _invoke_model)

    # Extract text from response
    text = getattr(response, "text", None)
    if not text:
        # Fallback to extracting text from candidates if necessary
        candidates = getattr(response, "candidates", None)
        if candidates:
            parts_text = []
            for candidate in candidates:
                content = getattr(candidate, "content", None)
                if content:
                    parts = getattr(content, "parts", [])
                    for part in parts:
                        part_text = getattr(part, "text", None)
                        if part_text:
                            parts_text.append(part_text)
            text = "\n".join(parts_text).strip()

    if not text:
        raise RuntimeError("Audio transcription response did not contain any text")

    logger.debug("Audio transcription completed (%d characters)", len(text))
    return text.strip()
