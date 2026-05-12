# Audio Transcription Prototype

This prototype demonstrates audio transcription using **Google Gemini 2.5 Flash** through **SAP Generative AI Hub**.

## Features

- ✅ Transcribe audio files (MP3, WAV, FLAC, AAC, OGG, M4A)
- ✅ Optional timestamp support for speaker identification
- ✅ Uses SAP Gen AI Hub native integration
- ✅ Automatic MIME type detection
- ✅ Saves transcription to text file

## Prerequisites

1. **Backend Environment**: The backend's `.venv` with `gen-ai-hub` already installed
2. **SAP AI Core Credentials**: Set up in backend `.env` file

## Setup

Simply activate the backend's virtual environment:

```bash
cd prototyping
source ../backend/.venv/bin/activate
```

## Configuration

The script uses the same SAP AI Core environment variables as the backend. Make sure these are set:

```bash
export AICORE_BASE_URL="https://api.ai.prod.ap-northeast-1.aws.ml.hana.ondemand.com/v2"
export AICORE_AUTH_URL="https://apjdl-aicorelp.authentication.jp10.hana.ondemand.com/oauth/token"
export AICORE_CLIENT_ID="your-client-id"
export AICORE_CLIENT_SECRET="your-client-secret"
export AICORE_RESOURCE_GROUP="your-resource-group"
```

Or source the backend `.env` file:

```bash
set -a
source ../backend/.env
set +a
```

## Usage

### Basic Transcription

```bash
python audio_transcription.py sample.mp3
```

### Transcription with Timestamps

```bash
python audio_transcription.py interview.wav --timestamps
```

### Download Sample Audio

```bash
python download_sample.py
```

This will download a sample MP3 file from Google Cloud samples.

## Example Output

### Without Timestamps
```
📁 Loading audio file: sample.mp3
📊 File size: 245.67 KB
🎵 MIME type: audio/mpeg
🔧 Initializing Gemini 2.5 Flash model...
🚀 Sending request to Gemini 2.5 Flash...
✅ Transcription complete!

📝 TRANSCRIPTION:
------------------------------------------------------------
Your devices are getting better over time. Welcome to the
Made by Google podcast where we meet the people who make
Google's products...
------------------------------------------------------------

💾 Transcription saved to: sample.txt
```

### With Timestamps
```
📝 TRANSCRIPTION:
------------------------------------------------------------
[00:00:00] **Speaker A:** Your devices are getting better over time.
[00:00:14] **Speaker B:** Welcome to the Made by Google podcast...
[00:00:20] **Speaker B:** Here's your host, Rasheed Finch.
------------------------------------------------------------
```

## Supported Audio Formats

| Format | Extension | MIME Type |
|--------|-----------|-----------|
| MP3 | `.mp3` | `audio/mpeg` |
| WAV | `.wav` | `audio/wav` |
| FLAC | `.flac` | `audio/flac` |
| AAC | `.aac` | `audio/aac` |
| OGG | `.ogg` | `audio/ogg` |
| M4A | `.m4a` | `audio/mp4` |

## How It Works

1. **File Loading**: The script reads your audio file and encodes it to base64
2. **MIME Detection**: Automatically detects the correct MIME type based on file extension
3. **SAP Gen AI Hub**: Uses the native Google Vertex AI integration through SAP's proxy
4. **Gemini 2.5 Flash**: Sends the audio to Gemini 2.5 Flash model for processing
5. **Response**: Returns the transcription text
6. **Save**: Automatically saves the transcription to a `.txt` file

## Technical Details

### Native Integration

This prototype uses the **native Google Vertex AI integration** from SAP Gen AI Hub SDK:

```python
from gen_ai_hub.proxy.native.google_vertexai.clients import GenerativeModel
from gen_ai_hub.proxy.core.proxy_clients import get_proxy_client

proxy_client = get_proxy_client('gen-ai-hub')
model = GenerativeModel(
    proxy_client=proxy_client,
    model_name='gemini-2.5-flash'
)
```

### Audio Data Format

Audio is sent as inline base64-encoded data:

```python
content = [{
    "role": "user",
    "parts": [
        {"text": "Transcribe this audio file."},
        {
            "inline_data": {
                "mime_type": "audio/mpeg",
                "data": base64_encoded_audio
            }
        }
    ]
}]
```

## Limitations

- **File Size**: Maximum file size depends on SAP AI Core limits (typically ~10 MB)
- **Duration**: Long audio files may take longer to process
- **Language**: Gemini 2.5 Flash supports multiple languages but accuracy varies
- **Model Availability**: Requires Gemini 2.5 Flash to be deployed in your SAP AI Core instance

## Troubleshooting

### Error: "Model not found"
- Ensure Gemini 2.5 Flash is deployed in your SAP AI Core instance
- Check the model name is exactly `gemini-2.5-flash`

### Error: "Authentication failed"
- Verify your SAP AI Core credentials in the environment variables
- Check that the resource group is correct

### Error: "File too large"
- Try compressing the audio file
- Use a shorter audio clip
- Convert to a more efficient format (e.g., MP3 with lower bitrate)

## Next Steps

This prototype can be extended to:
- Support streaming transcription for long files
- Add language detection and translation
- Integrate with the main chat application
- Support real-time audio input from microphone
- Add audio preprocessing (noise reduction, normalization)

## References

- [SAP Gen AI Hub SDK Documentation](../documentation/sap-gen-ai-hub-sdk/)
- [Google Gemini Audio Understanding](https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/audio-understanding)
- [Gemini 2.5 Flash Model](https://cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/2-5-flash)
