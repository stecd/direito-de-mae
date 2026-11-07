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


def forget(text: str, voice_id: str | None = None, history=None, pages: int = 3) -> int:
    """Delete this text's entries from ElevenLabs' speech history, which otherwise keeps the text
    of every reply in our account. Needs the API key's history read + write permission.
    Looks at up to `pages` x 20 of the newest items. Returns how many entries were deleted."""
    history = history or client.history
    gone, after = 0, None
    for _ in range(pages):
        page = history.list(page_size=20, voice_id=voice_id or os.environ.get("ELEVENLABS_VOICE_ID"),
                            sort_direction="desc", start_after_history_item_id=after)
        for item in page.history:
            if item.text == text:
                history.delete(item.history_item_id)
                gone += 1
        if gone or not getattr(page, "has_more", False) or not page.history:
            break
        after = page.history[-1].history_item_id
    return gone


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
