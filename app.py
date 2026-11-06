"""Direito de Mãe — WhatsApp webhook.

Run:   uvicorn app:app --port 8000
Tunnel: ngrok http --url=$NGROK_DOMAIN 8000
Twilio sandbox "When a message comes in": https://<NGROK_DOMAIN>/whatsapp  (POST)
"""
import base64
import logging
import os
import re
import traceback
import unicodedata
import uuid
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import httpx  # noqa: E402
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from twilio.request_validator import RequestValidator  # noqa: E402
from twilio.rest import Client  # noqa: E402

import brain  # noqa: E402
import dossie  # noqa: E402
import store  # noqa: E402
import voice  # noqa: E402

log = logging.getLogger("direito")
logging.basicConfig(level=logging.INFO)

SID = os.environ.get("TWILIO_ACCOUNT_SID") or "none"
TOKEN = os.environ.get("TWILIO_AUTH_TOKEN") or "none"
FROM = os.environ.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
PUBLIC_URL = os.environ.get("PUBLIC_URL", "").rstrip("/")
VALIDATE = os.environ.get("TWILIO_VALIDATE", "1") == "1"

twilio = Client(SID, TOKEN)
validator = RequestValidator(TOKEN)
app = FastAPI()

CONSENT = ("Oi! Eu sou o Direito de Mãe. Guardo o que você me mandar só para montar seu dossiê. "
           "Não guardo seu nome nem seu número. Mande APAGAR a qualquer hora para apagar tudo.")
EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


def command(text: str) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z]", "", t.upper())


import contextvars  # noqa: E402
OUTBOX: contextvars.ContextVar = contextvars.ContextVar("outbox", default=None)


def send(to: str, body: str = "", media: str | None = None) -> None:
    box = OUTBOX.get()
    if box is not None:  # web chat: collect replies instead of sending via Twilio
        box.append({"text": body, "media": media})
        return
    if os.environ.get("DRY_RUN") == "1":  # local testing: print instead of spending a Twilio message
        print(f"\n>>> REPLY: {body}" + (f"\n>>> MEDIA: {media}" if media else ""))
        return
    kw = {"from_": FROM, "to": to}
    if body:
        kw["body"] = body[:1500]
    if media:
        kw["media_url"] = [media]
    twilio.messages.create(**kw)


def media_url(uid: str, name: str) -> str:
    return f"{PUBLIC_URL}/media/{uid}/{name}"


@app.post("/whatsapp")
async def whatsapp(request: Request, tasks: BackgroundTasks):
    form = dict(await request.form())
    if VALIDATE:
        sig = request.headers.get("X-Twilio-Signature", "")
        if not validator.validate(f"{PUBLIC_URL}/whatsapp", form, sig):
            raise HTTPException(403, "bad signature")
    tasks.add_task(handle, form)
    # Answer Twilio immediately (it stops waiting after 15s); the real reply goes out later.
    return Response(EMPTY_TWIML, media_type="application/xml")


@app.get("/media/{uid}/{name}")
def media(uid: str, name: str):
    path = (store.DATA_DIR / uid / name).resolve()
    if store.DATA_DIR.resolve() not in path.parents or not path.exists():
        raise HTTPException(404)
    types = {".ogg": "audio/ogg", ".pdf": "application/pdf"}
    return FileResponse(path, media_type=types.get(path.suffix, "application/octet-stream"))


@app.get("/")
def web_page():
    return FileResponse(Path(__file__).parent / "web.html")


@app.post("/web")
async def web_chat(request: Request):
    """WhatsApp-style web chat: same handler, replies returned as JSON."""
    form = await request.form()
    data = {"From": "web:demo", "Body": form.get("text", ""), "NumMedia": "0"}
    up = form.get("file")
    if up is not None and hasattr(up, "read"):
        data.update(NumMedia="1", RawMedia=await up.read(),
                    MediaContentType0=(up.content_type or "").split(";")[0])
    box: list = []
    OUTBOX.set(box)
    import asyncio
    await asyncio.to_thread(contextvars.copy_context().run, handle, data)
    for m in box:  # web page loads media from this same server
        if m["media"] and PUBLIC_URL:
            m["media"] = m["media"].replace(PUBLIC_URL, "")
    return {"messages": box}


def handle(form: dict) -> None:
    to = form.get("From", "")
    try:
        _handle(form)
    except Exception:
        log.error(traceback.format_exc())
        send(to, "Tive um problema agora. Pode mandar de novo?")


def say(phone: str, uid: str, text: str, media: str | None = None) -> None:
    """Send the text (plus any file), then ALWAYS the same text as a voice note,
    so a mother who can't read still hears every answer."""
    send(phone, text, media)
    if not os.environ.get("ELEVENLABS_VOICE_ID"):
        return
    try:
        folder = store.DATA_DIR / "_shared" if uid == "_shared" else store.media_dir(uid)
        folder.mkdir(exist_ok=True)
        ogg = voice.speak(text, folder / f"resposta_{uuid.uuid4().hex[:8]}.ogg")
        send(phone, media=f"{PUBLIC_URL}/media/{folder.name}/{ogg.name}")
    except Exception:
        log.error("TTS failed, text already sent:\n%s", traceback.format_exc())


def _handle(form: dict) -> None:
    phone = form["From"]
    uid = store.user_id(phone)
    is_new = not store.exists(uid)
    text = (form.get("Body") or "").strip()

    # 1. Download media first, so a voice note can also be a command.
    raw, ctype, heard = None, "", ""
    if int(form.get("NumMedia", "0") or 0):
        ctype = form.get("MediaContentType0", "")
        if form.get("RawMedia") is not None:  # web chat upload
            raw = form["RawMedia"]
        elif form.get("LocalMedia"):  # simulate.py
            raw = Path(form["LocalMedia"]).read_bytes()
        else:
            raw = httpx.get(form["MediaUrl0"], auth=(SID, TOKEN), follow_redirects=True, timeout=30).content
        if ctype.startswith("audio/"):
            heard = voice.transcribe(raw)
            log.info("transcript: %s", heard)

    cmd = command(heard or text)

    # 2. Commands (typed or spoken).
    if cmd == "APAGAR" or (heard and "APAGAR" in cmd and len(cmd) < 40):
        store.delete(uid)
        say(phone, "_shared", "Pronto. Seus dados foram apagados.")
        return

    user = store.load(uid)

    if "DOSSI" in cmd and len(cmd) < 60:
        pdf = dossie.build(user, store.media_dir(uid) / "dossie.pdf")
        n = len(user["entries"])
        say(phone, uid, f"Aqui está seu dossiê com {n} registro(s). Leve ao sindicato ou à Defensoria. Não sou advogada.",
            media_url(uid, pdf.name))
        return

    # 3. Everything else goes to Claude.
    content: list = []
    history_note = text
    saved_file = None
    if raw is not None:
        ext = {"audio/ogg": ".ogg", "audio/webm": ".webm", "audio/mp4": ".m4a", "image/jpeg": ".jpg",
               "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}.get(ctype, "")
        saved_file = f"prova_{uuid.uuid4().hex[:8]}{ext}"
        (store.media_dir(uid) / saved_file).write_bytes(raw)
        if ctype.startswith("audio/"):
            history_note = f"[áudio] {heard}"
            content.append({"type": "text", "text": f"(Ela mandou um áudio. Transcrição:) {heard}"})
        elif ctype in ("image/jpeg", "image/png", "image/webp", "image/gif"):
            history_note = f"[print/foto enviado] {text}"
            content.append({"type": "image", "source": {"type": "base64", "media_type": ctype,
                                                        "data": base64.b64encode(raw).decode()}})
            content.append({"type": "text", "text": text or "(Ela mandou esta imagem, sem texto.)"})
    if not content:
        content.append({"type": "text", "text": text or "(mensagem vazia)"})

    out = brain.think(user["history"], content)

    if out.get("due_date"):
        user["profile"]["due_date"] = out["due_date"]
    reply = brain.fill_date(out.get("reply", ""), user["profile"].get("due_date"))

    if out.get("entry"):
        e = dict(out["entry"])
        e["date_logged"] = date.today().isoformat()
        if saved_file:
            e["file"] = saved_file
        user["entries"].append(e)
    if out.get("entry_update") and user["entries"]:
        user["entries"][-1].update(out["entry_update"])

    if is_new:
        reply = f"{CONSENT}\n\n{reply}"

    user["history"] += [{"role": "user", "content": history_note or "(vazio)"},
                        {"role": "assistant", "content": reply}]
    store.save(uid, user)

    say(phone, uid, reply)
