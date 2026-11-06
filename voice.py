"""ElevenLabs: speech-to-text (Scribe) and text-to-speech, plus ffmpeg -> voice note."""
import io
import os
import subprocess
from pathlib import Path

from elevenlabs.client import ElevenLabs

client = ElevenLabs()  # reads ELEVENLABS_API_KEY


def transcribe(audio: bytes) -> str:
    result = client.speech_to_text.convert(
        file=io.BytesIO(audio), model_id="scribe_v1", language_code="por"
    )
    return result.text


def speak(text: str, out_ogg: Path) -> Path:
    """Text -> mp3 (ElevenLabs) -> OGG Opus (WhatsApp voice-note format)."""
    chunks = client.text_to_speech.convert(
        voice_id=os.environ["ELEVENLABS_VOICE_ID"],
        text=text,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
    )
    mp3 = out_ogg.with_suffix(".mp3")
    mp3.write_bytes(b"".join(chunks))
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3),
         "-c:a", "libopus", "-b:a", "32k", "-ac", "1", "-ar", "48000", str(out_ogg)],
        check=True,
    )
    return out_ogg
