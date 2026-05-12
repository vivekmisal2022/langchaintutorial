#!/usr/bin/env python3
"""
Download a sample audio file for testing the transcription prototype.

This script downloads a sample MP3 file from Google Cloud samples.
"""

import urllib.request
from pathlib import Path


def download_sample_audio():
    """Download a sample audio file from Google Cloud."""
    # Sample audio URL from Google Cloud
    url = "https://storage.googleapis.com/cloud-samples-data/generative-ai/audio/pixel.mp3"
    output_file = Path(__file__).parent / "sample_pixel.mp3"
    
    print("=" * 60)
    print("📥 Downloading Sample Audio File")
    print("=" * 60)
    print()
    print(f"Source: {url}")
    print(f"Target: {output_file}")
    print()
    
    try:
        print("⏳ Downloading...")
        urllib.request.urlretrieve(url, output_file)
        
        file_size = output_file.stat().st_size
        print(f"✅ Download complete!")
        print(f"📊 File size: {file_size / 1024:.2f} KB")
        print()
        print("You can now test the transcription with:")
        print(f"  python audio_transcription.py {output_file.name}")
        print(f"  python audio_transcription.py {output_file.name} --timestamps")
        
    except Exception as e:
        print(f"❌ Error downloading file: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    download_sample_audio()
