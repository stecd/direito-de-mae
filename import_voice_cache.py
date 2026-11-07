"""Fill public/voice/ with ElevenLabs history clips whose text exactly matches a fixed message.

Run after rewording a fixed message, or on a new ElevenLabs account. Costs no credits.
Needs an API key with the speech_history_read permission.   Run: python import_voice_cache.py
"""
import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv(".env")
import app  # noqa: E402
from elevenlabs.client import ElevenLabs  # noqa: E402

c = ElevenLabs()
voice_id = os.environ.get("ELEVENLABS_VOICE_ID")
items, after = [], None
while True:
    h = c.history.list(page_size=1000, start_after_history_item_id=after)
    items += h.history
    if not h.has_more:
        break
    after = h.last_history_item_id
print(len(items), "history items")

app.VOICE_CACHE.mkdir(exist_ok=True)
done = set()
for i in items:
    t = i.text
    if t not in app.FIXED or t in done:
        continue
    if i.voice_id != voice_id:
        print("skip (other voice):", t[:50])
        continue
    mp3 = b"".join(c.history.get_audio(i.history_item_id))
    key = hashlib.sha256(f"{voice_id}|{t}".encode()).hexdigest()[:24]
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "a.mp3"
        src.write_bytes(mp3)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-c:a", "libopus",
                        "-b:a", "32k", "-ac", "1", "-ar", "48000", str(Path(tmp) / "a.ogg")], check=True)
        (app.VOICE_CACHE / f"{key}.ogg").write_bytes((Path(tmp) / "a.ogg").read_bytes())
    (app.VOICE_CACHE / f"{key}.mp3").write_bytes(mp3)
    done.add(t)
    print("cached:", t[:60].replace("\n", " "))
print(f"{len(done)} of {len(app.FIXED)} fixed messages cached")
for t in sorted(app.FIXED - done):
    print("  missing:", t[:60].replace("\n", " "))
