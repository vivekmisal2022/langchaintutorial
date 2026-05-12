#!/usr/bin/env python3
"""
Audio Transcription Prototype using Gemini 2.5 Flash via SAP Generative AI Hub.

This script demonstrates how to:
1. Upload an audio file (MP3, WAV, etc.)
2. Send it to Gemini 2.5 Flash model
3. Get back a text transcription

Supported audio formats: MP3, WAV, FLAC, AAC, OGG
"""

import base64
import sys, os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(filename="../backend/.env"))

from gen_ai_hub.proxy.native.google_genai.clients import Client, get_proxy_client


def encode_audio_file(file_path: Path) -> tuple[str, str]:
    """
    Encode audio file to base64 and determine MIME type.

    Args:
        file_path: Path to the audio file

    Returns:
        Tuple of (base64_data, mime_type)
    """
    # Map file extensions to MIME types
    mime_types = {
        '.mp3': 'audio/mpeg',
        '.wav': 'audio/wav',
        '.flac': 'audio/flac',
        '.aac': 'audio/aac',
        '.ogg': 'audio/ogg',
        '.m4a': 'audio/mp4',
    }

    suffix = file_path.suffix.lower()
    mime_type = mime_types.get(suffix, 'audio/mpeg')  # Default to MP3

    # Read and encode the file
    with open(file_path, 'rb') as f:
        audio_data = f.read()

    base64_data = base64.b64encode(audio_data).decode('utf-8')

    return base64_data, mime_type


def transcribe_audio(
    audio_file_path: str,
    prompt: str = "Transcribe this audio file. Provide the text content.",
    enable_timestamps: bool = False
) -> str:
    """
    Transcribe an audio file using Gemini 2.5 Flash.

    Args:
        audio_file_path: Path to the audio file
        prompt: Custom prompt for the model (default: simple transcription)
        enable_timestamps: Whether to include timestamps in transcription

    Returns:
        Transcription text from the model
    """
    file_path = Path(audio_file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

    print(f"📁 Loading audio file: {file_path.name}")
    print(f"📊 File size: {file_path.stat().st_size / 1024:.2f} KB")

    # Encode the audio file
    base64_data, mime_type = encode_audio_file(file_path)
    print(f"🎵 MIME type: {mime_type}")

    # Initialize the Gemini model via SAP Gen AI Hub
    print("🔧 Initializing Gemini 2.5 Flash model...")

    # Create proxy client with credentials
    proxy_client = get_proxy_client(
        proxy_version="gen-ai-hub",
        base_url=os.environ.get('AICORE_BASE_URL_US'),
        auth_url=os.environ.get('AICORE_AUTH_URL_US'),
        client_id=os.environ.get('AICORE_CLIENT_ID_US'),
        client_secret=os.environ.get('AICORE_CLIENT_SECRET_US'),
        resource_group=os.environ.get('AICORE_RESOURCE_GROUP_US'),
    )

    # Create the Google GenAI Client with proxy
    client = Client(proxy_client=proxy_client)

    # Prepare the content with inline audio data
    print("🚀 Sending request to Gemini 2.5 Flash...")

    contents = [{
        "role": "user",
        "parts": [
            {"text": prompt},
            {
                "inline_data": {
                    "mime_type": mime_type,
                    "data": base64_data
                }
            }
        ]
    }]

    # Generate content with optional timestamp support
    generation_config = {"audio_timestamp": True} if enable_timestamps else None

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        config=generation_config,
    )

    print("✅ Transcription complete!\n")

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

    return text.strip()


def main():
    """Main entry point for the audio transcription prototype."""
    print("=" * 60)
    print("🎙️  Audio Transcription Prototype")
    print("   Using Gemini 2.5 Flash via SAP Generative AI Hub")
    print("=" * 60)
    print()

    # Check command line arguments
    if len(sys.argv) < 2:
        print("Usage: python audio_transcription.py <audio_file_path> [--timestamps]")
        print()
        print("Examples:")
        print("  python audio_transcription.py sample.mp3")
        print("  python audio_transcription.py interview.wav --timestamps")
        print()
        print("Supported formats: MP3, WAV, FLAC, AAC, OGG, M4A")
        sys.exit(1)

    audio_file = sys.argv[1]
    enable_timestamps = '--timestamps' in sys.argv

    # Choose prompt based on timestamp option
    if enable_timestamps:
        prompt = """
        Transcribe this audio file in the format of timecode, speaker, caption.
        Use Speaker A, Speaker B, etc. to identify different speakers.
        """
    else:
        prompt = "Transcribe this audio file. Provide the complete text content."

    try:
        # Perform transcription
        transcription = transcribe_audio(
            audio_file,
            prompt=prompt,
            enable_timestamps=enable_timestamps
        )

        # Display results
        print("📝 TRANSCRIPTION:")
        print("-" * 60)
        print(transcription)
        print("-" * 60)

        # Optionally save to file
        output_file = Path(audio_file).with_suffix('.txt')
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(transcription)

        print(f"\n💾 Transcription saved to: {output_file}")

    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error during transcription: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
