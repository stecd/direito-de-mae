"""Go-live preflight. Sends NO WhatsApp messages and spends NO ElevenLabs credits.

    python golive/preflight.py            # local checks only (server may be off)
    python golive/preflight.py --live     # also checks the public URL + webhook signature (server + ngrok on)

Every line prints PASS / WARN / FAIL. Fix every FAIL before sending a single WhatsApp message.
"""
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

fails = 0


def check(ok, label, fix="", warn=False):
    global fails
    tag = "PASS" if ok else ("WARN" if warn else "FAIL")
    if not ok and not warn:
        fails += 1
    print(f"[{tag}] {label}" + ("" if ok or not fix else f"\n       → {fix}"))


# 1. Secrets and settings
mk = os.environ.get("MASTER_KEY", "")
try:
    from cryptography.fernet import Fernet
    Fernet(mk.encode())
    mk_ok = True
except Exception:
    mk_ok = False
check(mk_ok, "MASTER_KEY is set and valid",
      'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  → paste into .env as MASTER_KEY=...  and into your password manager')
check(not (ROOT / "data" / "_dev_master.key").exists(), "no development key left in data/",
      "delete data/_dev_master.key and data/_keys/ (test data only) BEFORE real users write")
salt = os.environ.get("HASH_SALT", "")
check(len(salt) >= 24 and salt != "troque-este-sal", "HASH_SALT is long and not the default",
      'python -c "import secrets; print(secrets.token_urlsafe(32))"  → .env HASH_SALT=...  (never change it after real users exist)')
for k in ("ANTHROPIC_API_KEY", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM", "PUBLIC_URL"):
    check(bool(os.environ.get(k)), f"{k} is set", f"add {k} to .env")
check(os.environ.get("TWILIO_VALIDATE", "1") == "1", "TWILIO_VALIDATE=1 (signature check on)", "set TWILIO_VALIDATE=1")
check(os.environ.get("DRY_RUN") != "1", "DRY_RUN is off in .env (real sends)", "remove DRY_RUN from .env", warn=True)
voice = os.environ.get("VOICE_REPLIES", "0") == "1"
print(f"[INFO] VOICE_REPLIES={'1 (voice replies ON: spends ElevenLabs credits)' if voice else '0 (text only: 0 credits)'}")
check(shutil.which("ffmpeg") is not None, "ffmpeg installed (voice notes)", "brew install ffmpeg")
check(shutil.which("ngrok") is not None, "ngrok installed", "brew install ngrok")

# 2. Encryption round trip with the real key
if mk_ok:
    import store
    uid = "_preflight_check"
    store.save(uid, {"history": [], "entries": [{"s": "x"}], "profile": {}})
    raw = (store.DATA_DIR / f"{uid}.json").read_bytes()
    ok = not raw.startswith(b"{") and store.load(uid)["entries"] == [{"s": "x"}]
    store.delete(uid)
    check(ok and not store.exists(uid), "encrypt → decrypt → shred works with MASTER_KEY")

# 3. Voice cache
import onboarding as ob  # noqa: E402
os.environ.setdefault("ELEVENLABS_API_KEY", "x")
import app  # noqa: E402
cached = sum(1 for f in (ROOT / "public" / "voice").glob("*.ogg"))
print(f"[INFO] voice cache: {cached} fixed messages cached in public/voice/")

# 4. Live: public URL and webhook signature (no messages sent)
if "--live" in sys.argv:
    import httpx
    url = os.environ.get("PUBLIC_URL", "").rstrip("/")
    try:
        r = httpx.get(url + "/", timeout=10, headers={"ngrok-skip-browser-warning": "1"})
        check(r.status_code == 200, f"public URL answers ({r.status_code})", "start: uvicorn app:app --port 8000  and  ngrok http --url=<your domain> 8000")
    except Exception as e:
        check(False, f"public URL answers ({type(e).__name__})", "start uvicorn and ngrok")
    try:
        r = httpx.post(url + "/whatsapp", data={"From": "whatsapp:+000", "Body": "preflight"},
                       headers={"X-Twilio-Signature": "forged"}, timeout=10)
        check(r.status_code == 403, f"forged webhook is rejected ({r.status_code}, expect 403)",
              "TWILIO_VALIDATE must be 1 and PUBLIC_URL must match the URL Twilio calls exactly")
    except Exception as e:
        check(False, f"forged webhook check ({type(e).__name__})")
    try:
        r = httpx.get(url + "/media/abc/resumo_x.pdf", timeout=10)
        check(r.status_code == 404, f"unsigned media link is refused ({r.status_code}, expect 404)")
    except Exception as e:
        check(False, f"media link check ({type(e).__name__})")

print(f"\n{'READY' if not fails else f'{fails} FAIL(s): fix before any WhatsApp message'}")
sys.exit(1 if fails else 0)
