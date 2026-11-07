"""Meta WhatsApp Cloud API adapter.

The rest of the bot speaks Twilio's webhook form ({"From", "Body", "NumMedia", ...}) and calls
send(to, body, media). This module turns Meta's webhook JSON into that form, and sends replies
through Meta's Graph API. Phones from Meta are written "meta:<wa_id>" so send() knows the channel.

.env: META_TOKEN, META_PHONE_ID, META_APP_SECRET, META_VERIFY_TOKEN (any string you choose),
      META_API_VERSION (default v23.0)
"""
import hashlib
import hmac
import logging
import os
import threading
import time
from collections import OrderedDict

import httpx

log = logging.getLogger("direito.meta")
PREFIX = "meta:"


def _cfg(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def graph(path: str) -> str:
    return f"https://graph.facebook.com/{_cfg('META_API_VERSION', 'v23.0')}/{path.lstrip('/')}"


def _auth() -> dict:
    return {"Authorization": f"Bearer {_cfg('META_TOKEN')}"}


# ---------- inbound ----------

def verify(params: dict) -> str | None:
    """Webhook verification GET: echo hub.challenge only if the verify token matches."""
    token = _cfg("META_VERIFY_TOKEN")
    if token and params.get("hub.mode") == "subscribe" and hmac.compare_digest(
            str(params.get("hub.verify_token", "")), token):
        return str(params.get("hub.challenge", ""))
    return None


def signature_ok(raw_body: bytes, header: str) -> bool:
    secret = _cfg("META_APP_SECRET")
    if not secret or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[len("sha256="):])


_SEEN: "OrderedDict[str, float]" = OrderedDict()
_SEEN_LOCK = threading.Lock()


def first_time(message_id: str) -> bool:
    """Meta retries webhooks; handle each message id once."""
    with _SEEN_LOCK:
        if message_id in _SEEN:
            return False
        _SEEN[message_id] = time.time()
        while len(_SEEN) > 2000:
            _SEEN.popitem(last=False)
        return True


def to_forms(payload: dict) -> list[dict]:
    """Meta webhook JSON → Twilio-style forms for app.handle(). Status updates are ignored."""
    forms = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for m in value.get("messages", []):
                who = m.get("from") or m.get("from_user_id")
                if not who or not first_time(m.get("id", "")):
                    continue
                form = {"From": PREFIX + who, "Body": "", "NumMedia": "0"}
                kind = m.get("type")
                if kind == "text":
                    form["Body"] = m.get("text", {}).get("body", "")
                elif kind in ("audio", "image", "document", "video", "sticker"):
                    media = m.get(kind, {})
                    form.update(NumMedia="1", MetaMediaId=media.get("id", ""),
                                MediaContentType0=(media.get("mime_type") or "").split(";")[0].strip())
                    form["Body"] = media.get("caption", "")
                else:
                    form["Body"] = ""  # reactions, locations…: treated as an empty message
                forms.append(form)
    return forms


def download(media_id: str, get=None) -> bytes | None:
    """Two steps: ask Meta for a short-lived URL, then fetch it with the same token."""
    get = get or httpx.get
    r = get(graph(media_id), headers=_auth(), timeout=30)
    if r.status_code != 200:
        log.error("meta media lookup refused: HTTP %s", r.status_code)
        return None
    url = r.json().get("url")
    f = get(url, headers=_auth(), timeout=30, follow_redirects=True)
    if f.status_code != 200:
        log.error("meta media download refused: HTTP %s", f.status_code)
        return None
    return f.content


# ---------- outbound ----------

_UPLOADED: list = []  # (media_id, uploaded_at): deleted from Meta by the janitor later
_UP_LOCK = threading.Lock()


def _post(payload: dict, post=None) -> dict:
    post = post or httpx.post
    payload = {"messaging_product": "whatsapp", "recipient_type": "individual", **payload}
    r = post(graph(f"{_cfg('META_PHONE_ID')}/messages"), headers=_auth(), json=payload, timeout=30)
    if r.status_code >= 300:
        # Meta's error JSON has codes, not her words; still, log only the code and type.
        err = (r.json() or {}).get("error", {}) if r.headers.get("content-type", "").startswith("application/json") else {}
        raise RuntimeError(f"meta send failed: HTTP {r.status_code} code {err.get('code')} {err.get('type')}")
    return r.json()


def upload(data: bytes, mime: str, filename: str, post=None) -> str:
    post = post or httpx.post
    r = post(graph(f"{_cfg('META_PHONE_ID')}/media"), headers=_auth(),
             data={"messaging_product": "whatsapp", "type": mime},
             files={"file": (filename, data, mime)}, timeout=60)
    if r.status_code >= 300:
        raise RuntimeError(f"meta upload failed: HTTP {r.status_code}")
    media_id = r.json()["id"]
    with _UP_LOCK:
        _UPLOADED.append((media_id, time.time()))
    return media_id


def send(to: str, body: str = "", media: tuple | None = None, post=None) -> None:
    """to: 'meta:<wa_id>'. media: (bytes, filename) read from our encrypted store, or None.
    Voice notes go as real voice messages; PDFs as documents with the text as caption."""
    wa_id = to[len(PREFIX):]
    if media:
        data, name = media
        if name.endswith(".ogg"):
            if body:
                _post({"to": wa_id, "type": "text", "text": {"body": body[:4000]}}, post)
            mid = upload(data, "audio/ogg", name, post)
            _post({"to": wa_id, "type": "audio", "audio": {"id": mid, "voice": True}}, post)
        elif name.endswith(".pdf"):
            mid = upload(data, "application/pdf", "resumo.pdf", post)
            doc = {"id": mid, "filename": "resumo.pdf"}
            if body:
                doc["caption"] = body[:1000]
            _post({"to": wa_id, "type": "document", "document": doc}, post)
        else:
            mid = upload(data, "image/jpeg", name, post)
            _post({"to": wa_id, "type": "image", "image": {"id": mid, "caption": body[:1000]}}, post)
        return
    if body:
        _post({"to": wa_id, "type": "text", "text": {"body": body[:4000]}}, post)


def cleanup_uploads(now: float | None = None, delete=None, older_than: float = 600) -> int:
    """Meta keeps uploaded media for 30 days. Delete ours once WhatsApp has delivered it."""
    now = time.time() if now is None else now
    delete = delete or (lambda mid: httpx.delete(graph(mid), headers=_auth(), timeout=30))
    with _UP_LOCK:
        due = [x for x in _UPLOADED if now - x[1] >= older_than]
        _UPLOADED[:] = [x for x in _UPLOADED if now - x[1] < older_than]
    gone = 0
    for mid, _ in due:
        try:
            delete(mid)
            gone += 1
        except Exception:
            log.error("meta: could not delete an uploaded media item")
    return gone


def configured() -> bool:
    return all(_cfg(k) for k in ("META_TOKEN", "META_PHONE_ID", "META_APP_SECRET", "META_VERIFY_TOKEN"))
