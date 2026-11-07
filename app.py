"""Direito de Mãe — WhatsApp webhook.

Run:   uvicorn app:app --port 8000
Tunnel: ngrok http --url=$NGROK_DOMAIN 8000
Twilio sandbox "When a message comes in": https://<NGROK_DOMAIN>/whatsapp  (POST)

Logs never contain message text, transcripts or phone numbers: only event names and errors.
"""
import asyncio
import base64
import contextvars
import hashlib
import hmac
import json
import logging
import os
import re
import tempfile
import time
import threading
import traceback
import unicodedata
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime
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
import onboarding as ob  # noqa: E402
import store  # noqa: E402
import voice  # noqa: E402

log = logging.getLogger("direito")
logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)  # its request lines carry media URLs

SID = os.environ.get("TWILIO_ACCOUNT_SID") or "none"
TOKEN = os.environ.get("TWILIO_AUTH_TOKEN") or "none"
FROM = os.environ.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
PUBLIC_URL = os.environ.get("PUBLIC_URL", "").rstrip("/")
VALIDATE = os.environ.get("TWILIO_VALIDATE", "1") == "1"
LINK_TTL = 15 * 60          # media links stop working after 15 minutes
CONFIRM_TTL = 10 * 60       # "send APAGAR again" must come within 10 minutes
CLEANUP_EVERY = 10 * 60     # retention sweep + Twilio cleanup

twilio = Client(SID, TOKEN)
validator = RequestValidator(TOKEN)

EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
DELETE_ASK = ("Você quer mesmo apagar tudo? Seus registros e o resumo somem para sempre e não dá para recuperar. "
              "Mande APAGAR de novo para confirmar. Se quiser uma cópia antes, mande RESUMO.")
DELETED = "Pronto. Seus dados foram apagados."
NOTHING = "Não tenho nada guardado seu."
SAVED = ("Combinado. Vou guardar seus registros por 1 ano depois da sua última mensagem. "
         "Para apagar antes, é só pedir.")


def scrubbed_tb() -> str:
    """Traceback with file/line/function and the exception TYPE only. Exception messages can
    echo her words (a bad date, model output), so they never reach the log."""
    import sys
    etype, _, tb = sys.exc_info()
    frames = "".join(f"  {f.filename.rsplit('/', 1)[-1]}:{f.lineno} in {f.name}\n" for f in traceback.extract_tb(tb))
    return f"{frames}{etype.__name__ if etype else 'Error'}"


def command(text: str) -> str:
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z]", "", t.upper())


SID_RE = re.compile(r"[a-zA-Z0-9-]{8,64}")
MAX_UPLOAD = 10 * 1024 * 1024
MAX_TEXT = 2000
UNSUPPORTED = "Ainda não consigo ler esse tipo de arquivo. Mande print, foto, áudio ou escreva."
IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp", "image/gif")


def valid_sid(sid) -> bool:
    return isinstance(sid, str) and bool(SID_RE.fullmatch(sid))


RESUMO_WORDS = ("RESUMO", "DOSSI", "RELATORIO", "MINHASPROVAS")


def wants_resumo(cmd: str, spoken: bool) -> bool:
    """Short messages only; longer ones go to Claude, which reads the intent."""
    if len(cmd) >= 60:
        return False
    if any(w in cmd for w in RESUMO_WORDS):
        return True
    # Scribe sometimes hears "dossiê" as "doce"; accept only with MEU/QUERO/MANDA.
    return spoken and "DOCE" in cmd and any(w in cmd for w in ("MEU", "QUERO", "MANDA"))


def says_apagar(cmd: str) -> bool:
    """Spoken 'apagar' only when it leads the sentence and nothing negates it:
    'não, não quero apagar não' must never count."""
    return len(cmd) < 40 and "NAO" not in cmd and cmd.startswith(("APAGAR", "QUEROAPAGAR", "PODEAPAGAR", "SIMAPAGAR"))


def confirms_delete(cmd: str) -> bool:
    return cmd in ("APAGAR", "SIM", "SIMAPAGAR", "PODEAPAGAR") or says_apagar(cmd)


def keyword(cmd: str, spoken: bool) -> str | None:
    """Exact shortcut words skip the AI call. Anything else goes to Claude for intent."""
    if cmd == "APAGAR" or (spoken and says_apagar(cmd)):
        return "apagar"
    if cmd == "SALVAR":
        return "salvar"
    if cmd == "MUDAR":
        return "mudar_modo"
    if cmd in ("MEUSDADOS", "DADOS"):
        return "meus_dados"
    if wants_resumo(cmd, spoken):
        return "resumo"
    return None


class RateLimiter:
    def __init__(self, limit: int = 20, window: float = 600):
        self.limit, self.window, self.hits = limit, window, {}

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        q = [t for t in self.hits.get(key, []) if now - t < self.window]
        ok = len(q) < self.limit
        if ok:
            q.append(now)
        self.hits[key] = q
        return ok


LIMITER = RateLimiter(limit=80, window=600)  # shared demo Wi-Fi: ~80 msgs per 10 min per IP
OUTBOX: contextvars.ContextVar = contextvars.ContextVar("outbox", default=None)


# ---------- Twilio cleanup: Twilio keeps every message and its media unless we delete them ----------

CLEANUP_FILE = store.DATA_DIR / "_twilio_cleanup.json"  # message SIDs only, no content


CLEANUP_LOCK = threading.Lock()


def _queue_cleanup(sid: str) -> None:
    with CLEANUP_LOCK:
        q = _load_cleanup()
        q.append({"sid": sid, "at": time.time(), "tries": 0})
        CLEANUP_FILE.write_text(json.dumps(q))


def _load_cleanup() -> list:
    try:
        return json.loads(CLEANUP_FILE.read_text())
    except (OSError, ValueError):
        return []


def twilio_cleanup(now: float | None = None, client=None) -> int:
    """Delete queued messages (and with them their media) once Twilio is done delivering
    them. Outbound messages can't be deleted while still sending, so wait 2 minutes and
    retry failures a few times. Returns how many were deleted."""
    now = time.time() if now is None else now
    client = client or twilio
    with CLEANUP_LOCK:
        queue = _load_cleanup()
    keep, done = [], 0
    for item in queue:
        if now - item["at"] < 120:
            keep.append(item)
            continue
        try:
            client.messages(item["sid"]).delete()
            done += 1
        except Exception as e:
            item["tries"] += 1
            if getattr(e, "status", None) == 404:
                continue  # already gone
            if item["tries"] < 6:
                keep.append(item)
            else:
                log.error("twilio cleanup gave up on a message after 6 tries")
    # Rewrite only at the end: a crash mid-loop keeps every SID for the next run.
    # SIDs queued by handlers meanwhile are kept too.
    seen = {i["sid"] for i in queue}
    with CLEANUP_LOCK:
        CLEANUP_FILE.write_text(json.dumps(keep + [i for i in _load_cleanup() if i["sid"] not in seen]))
    return done


async def _janitor():
    while True:
        try:
            gone = store.sweep()
            if gone:
                log.info("retention: deleted %d expired user(s)", len(gone))
            if SID != "none" and os.environ.get("DRY_RUN") != "1":
                twilio_cleanup()
            prune_locks()
        except Exception:
            log.error("janitor failed:\n%s", scrubbed_tb())
        await asyncio.sleep(CLEANUP_EVERY)


@asynccontextmanager
async def lifespan(_app):
    task = asyncio.create_task(_janitor())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)


# ---------- Sending ----------

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
    msg = twilio.messages.create(**kw)
    _queue_cleanup(msg.sid)


def _sign(uid: str, name: str, exp: int) -> str:
    return hmac.new(store.secret(), f"{uid}/{name}/{exp}".encode(), hashlib.sha256).hexdigest()[:32]


def media_url(uid: str, name: str, now: float | None = None) -> str:
    """Signed link that stops working after LINK_TTL, so a forwarded or guessed link is useless."""
    exp = int((time.time() if now is None else now) + LINK_TTL)
    return f"{PUBLIC_URL}/media/{uid}/{name}?exp={exp}&sig={_sign(uid, name, exp)}"


def link_ok(uid: str, name: str, exp: str, sig: str, now: float | None = None) -> bool:
    try:
        e = int(exp)
    except (TypeError, ValueError):
        return False
    now = time.time() if now is None else now
    return e >= now and hmac.compare_digest(_sign(uid, name, e), str(sig))


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
def media(uid: str, name: str, exp: str = "", sig: str = ""):
    if not link_ok(uid, name, exp, sig):
        raise HTTPException(404)
    data = store.read_media(uid, name)
    if data is None:
        raise HTTPException(404)
    types = {".ogg": "audio/ogg", ".mp3": "audio/mpeg", ".pdf": "application/pdf"}
    return Response(data, media_type=types.get(Path(name).suffix, "application/octet-stream"),
                    headers={"Cache-Control": "no-store"})


@app.get("/")
def web_page():
    return FileResponse(Path(__file__).parent / "web.html")


@app.post("/web")
async def web_chat(request: Request):
    """WhatsApp-style web chat: same handler, replies returned as JSON."""
    form = await request.form()
    sid = form.get("sid")
    if not valid_sid(sid):
        raise HTTPException(400, "bad sid")
    ip = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip() or (
        request.client.host if request.client else "?")
    if not LIMITER.allow(ip):
        return {"messages": [{"text": "Muitas mensagens em pouco tempo. Espere uns minutos e tente de novo.", "media": None}]}
    body = str(form.get("text", ""))[:MAX_TEXT]
    data = {"From": f"web:{sid}", "Body": body, "NumMedia": "0"}
    up = form.get("file")
    if up is not None and hasattr(up, "read"):
        raw = await up.read(MAX_UPLOAD + 1)
        if len(raw) > MAX_UPLOAD:
            return {"messages": [{"text": "Esse arquivo é muito grande (máximo 10 MB). Tente um print ou um áudio mais curto.", "media": None}]}
        data.update(NumMedia="1", RawMedia=raw,
                    MediaContentType0=(up.content_type or "").split(";")[0])
    box: list = []
    OUTBOX.set(box)
    await asyncio.to_thread(contextvars.copy_context().run, handle, data)
    for m in box:  # web page loads media from this same server
        if m["media"] and PUBLIC_URL:
            m["media"] = m["media"].replace(PUBLIC_URL, "")
    return {"messages": box}


_LOCKS: dict = {}
_LOCKS_GUARD = threading.Lock()


def user_lock(uid: str) -> threading.Lock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(uid, threading.Lock())


def prune_locks() -> None:
    """Forget locks nobody holds, so memory doesn't keep every user id that ever wrote."""
    with _LOCKS_GUARD:
        for uid in [u for u, lk in _LOCKS.items() if not lk.locked()]:
            del _LOCKS[uid]


def handle(form: dict) -> None:
    to = form.get("From", "")
    try:
        with user_lock(store.user_id(to)):  # one message at a time per user
            _handle(form)
    except Exception:
        log.error("handler failed:\n%s", scrubbed_tb())
        send(to, "Tive um problema agora. Pode mandar de novo?")
    finally:
        msid = form.get("MessageSid")
        if msid and SID != "none" and os.environ.get("DRY_RUN") != "1":
            _queue_cleanup(msid)  # her message and its media leave Twilio too


def voice_on() -> bool:
    """Voice replies need a voice ID and VOICE_REPLIES=1 (off by default to save ElevenLabs credits).
    Incoming voice notes are still transcribed either way."""
    return bool(os.environ.get("ELEVENLABS_VOICE_ID")) and os.environ.get("VOICE_REPLIES", "0") == "1"


# Messages that are always the same: their voice notes are made once and reused.
# They hold nothing about her, so the cache is shared, unencrypted and kept in git (public/voice/).
FIXED = {ob.WELCOME + "\n\n" + ob.MODE_Q, ob.MODE_AGAIN, ob.CONSENT_AGAIN, ob.CONSENT_NO, ob.SAFETY_TIP,
         ob.MODE_CHANGE_Q, DELETE_ASK, DELETED, SAVED, NOTHING,
         *ob.MODE_OK.values(), *(f"{v} {ob.CONSENT_Q}" for v in ob.MODE_OK.values())}
VOICE_CACHE = Path(__file__).parent / "public" / "voice"  # committed to git: no personal data


def spoken(text: str) -> tuple[bytes, bytes]:
    """(ogg, mp3) for text. Fixed messages come from the cache after the first time."""
    key = hashlib.sha256(f"{os.environ.get('ELEVENLABS_VOICE_ID')}|{text}".encode()).hexdigest()[:24]
    ogg_f, mp3_f = VOICE_CACHE / f"{key}.ogg", VOICE_CACHE / f"{key}.mp3"
    if text in FIXED and ogg_f.exists() and mp3_f.exists():
        return ogg_f.read_bytes(), mp3_f.read_bytes()
    with tempfile.TemporaryDirectory() as tmp:
        ogg = voice.speak(text, Path(tmp) / "r.ogg")
        pair = ogg.read_bytes(), ogg.with_suffix(".mp3").read_bytes()
    if text in FIXED:
        VOICE_CACHE.mkdir(exist_ok=True)
        ogg_f.write_bytes(pair[0])
        mp3_f.write_bytes(pair[1])
    return pair


def say(phone: str, uid: str, text: str, media: str | None = None, mode: str | None = None) -> None:
    """Reply the way she asked for in onboarding.
    text  -> written message only
    audio -> voice note (written text only alongside a file, or if the voice fails)
    both / not chosen yet -> written message, then the same as a voice note"""
    mode = mode or ob.BOTH
    tts = voice_on() and mode != ob.TEXT
    if mode != ob.AUDIO or media or not tts:
        send(phone, text, media)
        sent_text = True
    else:
        sent_text = False
    if not tts:
        return
    try:
        ogg, mp3 = spoken(text)
        base = f"resposta_{uuid.uuid4().hex[:8]}"
        if OUTBOX.get() is not None:  # web chat: mp3 plays in every browser (Safari can't play ogg)
            name = store.write_media(uid, base + ".mp3", mp3)
        else:  # WhatsApp: OGG Opus shows as a voice-note bubble
            name = store.write_media(uid, base + ".ogg", ogg)
        send(phone, media=media_url(uid, name))
    except Exception:
        log.error("TTS failed:\n%s", scrubbed_tb())
        if not sent_text:
            send(phone, text, media)


def _expiry(user: dict) -> str:
    return datetime.fromtimestamp(store.expires_at(user)).strftime("%d/%m/%Y")


WORK_TYPE_WORDS = {"clt": "trabalha com carteira", "domestica": "é empregada doméstica",
                   "servidora": "é servidora pública", "autonoma": "trabalha por conta própria",
                   "desempregada": "estava sem emprego antes da gravidez", "rural": "é trabalhadora rural"}


def my_data(user: dict) -> str:
    n = len(user["entries"])
    files = sum(1 for e in user["entries"] if e.get("file"))
    how = {"text": "mensagem escrita", "audio": "áudio", "both": "mensagem escrita e áudio"}.get(
        user["profile"].get("mode"), "mensagem escrita e áudio")
    due = user["profile"].get("due_date")
    parts = [f"Tenho guardado: {n} registro(s), {files} print(s) ou áudio(s)"]
    if due:
        parts.append(f"a data prevista do parto ({date.fromisoformat(due):%d/%m/%Y})")
    wt = WORK_TYPE_WORDS.get(user["profile"].get("work_type"))
    if wt:
        parts.append(f"que você {wt} (se estiver errado, me diga)")
    parts.append(f"e que você prefere {how}")
    return (", ".join(parts) + ". Não guardo seu número. "
            f"Se você não falar comigo até {_expiry(user)}, eu apago tudo. "
            "Mande RESUMO para receber uma cópia, SALVAR para guardar por mais tempo, ou APAGAR para apagar agora.")


def _resumo(phone: str, uid: str, user: dict, mode: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        pdf = dossie.build(user, Path(tmp) / "resumo.pdf", read=lambda f: store.read_media(uid, f))
        name = store.write_media(uid, f"resumo_{uuid.uuid4().hex[:8]}.pdf", pdf.read_bytes())
    n = len(user["entries"])
    say(phone, uid, f"Aqui está seu resumo com {n} registro(s). Leve ao sindicato ou à Defensoria. "
        "Não sou advogada. O link vale por 15 minutos: salve o arquivo no seu celular.",
        media_url(uid, name), mode=mode)


def run_intent(intent: str, phone: str, uid: str, user: dict) -> None:
    """Commands, whether she typed the shortcut word or said it in her own words."""
    mode = user["profile"].get("mode")
    if intent == "apagar":
        user["profile"]["pending_delete"] = time.time()
        store.save(uid, user)
        say(phone, uid, DELETE_ASK, mode=mode)
    elif intent == "salvar":
        user["profile"]["keep_days"] = store.SAVED_KEEP_DAYS
        store.save(uid, user)
        say(phone, uid, SAVED, mode=mode)
    elif intent == "mudar_modo":
        user["profile"]["onboarding"] = "mode_change"
        store.save(uid, user)
        say(phone, uid, ob.MODE_CHANGE_Q, mode=ob.BOTH)  # ask in both: she may be switching away
    elif intent == "meus_dados":
        store.save(uid, user)
        say(phone, uid, my_data(user), mode=mode)
    elif intent == "resumo":
        store.save(uid, user)
        _resumo(phone, uid, user, mode)


def _download(form: dict, phone: str):
    """Returns (raw, ctype, heard) or None if a reply was already sent."""
    raw, ctype, heard = None, "", ""
    if int(form.get("NumMedia", "0") or 0):
        ctype = form.get("MediaContentType0", "")
        if form.get("RawMedia") is not None:  # web chat upload
            raw = form["RawMedia"]
        elif form.get("LocalMedia"):  # simulate.py
            raw = Path(form["LocalMedia"]).read_bytes()
        else:
            raw = httpx.get(form["MediaUrl0"], auth=(SID, TOKEN), follow_redirects=True, timeout=30).content
        if not (ctype.startswith("audio/") or ctype in IMAGE_TYPES):
            send(phone, UNSUPPORTED)
            return None
        if ctype.startswith("audio/"):
            try:
                heard = voice.transcribe(raw)
            except Exception:
                log.error("STT failed:\n%s", scrubbed_tb())
                send(phone, "Não consegui ouvir esse áudio. Pode mandar de novo?")
                return None
    return raw, ctype, heard


def _onboard(phone: str, uid: str, user: dict, said: str, spoken: bool, is_new: bool) -> bool:
    """Runs the interview. Returns True when this message was part of it (reply sent)."""
    p = user["profile"]
    step = p.get("onboarding")
    if is_new:
        # First contact: we don't know yet whether she reads or listens, so ask in both.
        # Keep only what she said (text or transcript) to answer it after she agrees.
        p["onboarding"] = "mode"
        if len(said.split()) > 3:  # a greeting ("oi", "bom dia") needs no second answer after consent
            p["pending_first"] = said.strip()[:600]
        store.save(uid, user)
        say(phone, uid, f"{ob.WELCOME}\n\n{ob.MODE_Q}", mode=ob.BOTH)
        return True
    if step == "mode_change" and (keyword(command(said), spoken) or len(said.split()) > 8):
        p["onboarding"] = "done"  # she moved on: treat this as a normal message
        return False
    if step in ("mode", "mode_change"):
        m = ob.parse_mode(said, spoken) if len(said.split()) <= 8 else None
        if m is None:
            if step == "mode" and len(said.split()) > 3 and not p.get("pending_first"):
                p["pending_first"] = said.strip()[:600]
            store.save(uid, user)
            say(phone, uid, ob.MODE_AGAIN, mode=ob.BOTH)
            return True
        p["mode"] = m
        if step == "mode":
            p["onboarding"] = "consent"
            store.save(uid, user)
            say(phone, uid, f"{ob.MODE_OK[m]} {ob.CONSENT_Q}", mode=m)
        else:
            p["onboarding"] = "done"
            store.save(uid, user)
            say(phone, uid, ob.MODE_OK[m], mode=m)
        return True
    if step == "consent":
        if ob.is_yes(said):
            p["onboarding"] = "done"
            p["consented"] = date.today().isoformat()
            first = p.pop("pending_first", None)
            store.save(uid, user)
            say(phone, uid, ob.SAFETY_TIP, mode=p.get("mode"))
            if first:
                _converse(phone, uid, user, text=first, content=[{"type": "text", "text": first}],
                          history_note=first)
            return True
        if ob.is_no(said):
            store.delete(uid)
            say(phone, "_shared", ob.CONSENT_NO, mode=p.get("mode"))
            return True
        store.save(uid, user)
        say(phone, uid, ob.CONSENT_AGAIN, mode=p.get("mode"))
        return True
    return False


def _handle(form: dict) -> None:
    phone = form["From"]
    uid = store.user_id(phone)
    is_new = not store.exists(uid)
    text = (form.get("Body") or "").strip()

    # 1. Download media first, so a voice note can also be a command or an onboarding answer.
    got = _download(form, phone)
    if got is None:
        return
    raw, ctype, heard = got
    said = heard or text
    cmd = command(said)
    try:
        user = store.load(uid)
    except store.Unreadable:
        log.error("a user file could not be decrypted (MASTER_KEY changed?)")
        if keyword(cmd, bool(heard)) == "apagar":
            store.delete(uid)
            say(phone, "_shared", DELETED)
        else:
            send(phone, "Não consigo abrir o que você guardou antes. Mande APAGAR para apagar tudo e começar de novo.")
        return
    p = user["profile"]

    # 2. A pending delete is confirmed only by APAGAR (or SIM) sent again within 10 minutes.
    pending = p.pop("pending_delete", None)
    if pending and time.time() - pending < CONFIRM_TTL and confirms_delete(cmd):
        mode = p.get("mode")
        store.delete(uid)
        say(phone, "_shared", DELETED, mode=mode)
        return

    if is_new and cmd == "APAGAR":
        send(phone, NOTHING)
        return

    # 3. Onboarding interview (new users, consent, changing text/audio).
    if p.get("onboarding") in ("mode", "consent") and keyword(cmd, bool(heard)) == "apagar":
        store.delete(uid)  # nothing of hers is kept yet beyond her first message
        say(phone, "_shared", DELETED, mode=p.get("mode"))
        return
    if _onboard(phone, uid, user, said, bool(heard), is_new):
        return

    # 4. Shortcut words skip the AI call.
    kw = keyword(cmd, bool(heard))
    if kw:
        run_intent(kw, phone, uid, user)
        return

    # 5. Everything else goes to Claude.
    content: list = []
    history_note = text
    saved_file = None
    if raw is not None:
        ext = {"audio/ogg": ".ogg", "audio/webm": ".webm", "audio/mp4": ".m4a", "image/jpeg": ".jpg",
               "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}.get(ctype, "")
        saved_file = store.write_media(uid, f"prova_{uuid.uuid4().hex[:8]}{ext}", raw)
        if ctype.startswith("audio/"):
            history_note = f"[áudio] {heard}"
            content.append({"type": "text", "text": f"(Ela mandou um áudio. Transcrição:) {heard}"})
        elif ctype in IMAGE_TYPES:
            history_note = f"[print/foto enviado] {text}"
            content.append({"type": "image", "source": {"type": "base64", "media_type": ctype,
                                                        "data": base64.b64encode(raw).decode()}})
            content.append({"type": "text", "text": text or "(Ela mandou esta imagem, sem texto.)"})
    if not content:
        content.append({"type": "text", "text": text or "(mensagem vazia)"})
    _converse(phone, uid, user, text, content, history_note, saved_file)


def _converse(phone: str, uid: str, user: dict, text: str, content: list, history_note: str,
              saved_file: str | None = None) -> None:
    out = brain.think(user["history"], content, user["entries"], user["profile"].get("work_type"))

    if out.get("due_date"):
        try:
            date.fromisoformat(str(out["due_date"]))
            user["profile"]["due_date"] = out["due_date"]
        except ValueError:
            log.warning("ignoring a bad due_date from the model")
    if out.get("work_type") in brain.WORK_TYPES:
        user["profile"]["work_type"] = out["work_type"]
    raw_reply = str(out.get("reply", ""))[:900]
    reply = brain.fill_date(raw_reply, user["profile"].get("due_date"))

    if out.get("entry"):
        e = dict(out["entry"])
        e["date_logged"] = date.today().isoformat()
        if saved_file:
            e["file"] = saved_file
        user["entries"].append(e)
        if saved_file and e.get("summary"):
            history_note = (f"[{e.get('source', 'print')} enviado; você leu a imagem nesta hora e registrou: "
                            f"{e['summary']}] {text}").strip()
    if out.get("entry_update") and user["entries"]:
        user["entries"][-1].update(out["entry_update"])

    user["history"] += [{"role": "user", "content": history_note or "(vazio)"},
                        # Store what Claude actually wrote (with the date tag, as JSON) so later turns
                        # don't see dates "it wrote" against its own rules and try to correct them.
                        {"role": "assistant", "content": json.dumps({"reply": raw_reply}, ensure_ascii=False)}]

    intent = out.get("intent")
    if intent in brain.INTENTS:
        # She asked in her own words; the code does the action (and asks before deleting).
        run_intent(intent, phone, uid, user)
        return

    store.save(uid, user)
    say(phone, uid, reply, mode=user["profile"].get("mode"))
