"""ElevenLabs: speech-to-text (Scribe) and text-to-speech, plus ffmpeg -> voice note."""
import io
import logging
import os
import subprocess
from pathlib import Path

from elevenlabs.client import ElevenLabs

client = ElevenLabs()  # reads ELEVENLABS_API_KEY
log = logging.getLogger("direito.voice")


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


def forget_id(history_item_id: str, history=None) -> None:
    """Delete exactly one history item: the one ElevenLabs created for this reply."""
    (history or client.history).delete(history_item_id)


def speak(text: str, out_ogg: Path, on_history_id=None) -> Path:
    """Text -> mp3 (ElevenLabs) -> OGG Opus (WhatsApp voice-note format).
    on_history_id(id) is called as soon as ElevenLabs answers, before the audio downloads, with the
    id of the history item it created, so the caller can delete exactly that item even if the
    download or ffmpeg fails later."""
    with client.text_to_speech.with_raw_response.convert(
        voice_id=os.environ["ELEVENLABS_VOICE_ID"],
        text=text,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
    ) as resp:
        hid = resp.headers.get("history-item-id")
        if not hid:
            log.warning("voice: ElevenLabs sent no history-item-id; deletion falls back to text matching")
        elif on_history_id:
            on_history_id(hid)
        audio = b"".join(resp.data)
    mp3 = out_ogg.with_suffix(".mp3")
    mp3.write_bytes(audio)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3),
         "-c:a", "libopus", "-b:a", "32k", "-ac", "1", "-ar", "48000", str(out_ogg)],
        check=True,
    )
    return out_ogg
