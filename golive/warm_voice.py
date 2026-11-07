"""Voice the fixed messages that aren't cached yet, so the demo spends credits only on real answers.
Sends no WhatsApp messages.

    python golive/warm_voice.py          # shows what's missing and the exact credit cost; spends nothing
    python golive/warm_voice.py --yes    # generates them (1 credit per character)

Only messages that can be spoken are counted: replies to someone who chose written messages
are never voiced. Run python import_voice_cache.py first: clips already in ElevenLabs history are free.
"""
import hashlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
import app  # noqa: E402
import onboarding as ob  # noqa: E402

voice_id = os.environ.get("ELEVENLABS_VOICE_ID")
never_spoken = {ob.MODE_OK[ob.TEXT], f"{ob.MODE_OK[ob.TEXT]} {ob.CONSENT_Q}",
                app.NOTHING}  # NOTHING goes out with send(), never voiced
missing = []
for t in sorted(app.FIXED - never_spoken):
    key = hashlib.sha256(f"{voice_id}|{t}".encode()).hexdigest()[:24]
    if not (app.VOICE_CACHE / f"{key}.ogg").exists():
        missing.append(t)
cost = sum(len(t) for t in missing)
print(f"{len(missing)} fixed message(s) not cached, {cost} characters ≈ {cost} credits:")
for t in missing:
    print(f"  {len(t):4d}  {t[:70].replace(chr(10), ' ')}…")
if "--yes" in sys.argv and missing:
    for t in missing:
        app.spoken(t)
        print("  voiced:", t[:50].replace("\n", " "))
    print("done: commit public/voice/ so they're never paid for again")
elif missing:
    print("nothing spent. Re-run with --yes to generate.")
