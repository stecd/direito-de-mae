"""Meta WhatsApp Cloud API adapter: no network calls (Graph requests are faked)."""
import hashlib
import hmac
import json
import os
from types import SimpleNamespace as NS

os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.update(META_TOKEN="tok", META_PHONE_ID="PNID", META_APP_SECRET="sekret", META_VERIFY_TOKEN="vt")

import pytest  # noqa: E402

import app  # noqa: E402
import meta  # noqa: E402
import store  # noqa: E402


def _msg(mid, **m):
    return {"object": "whatsapp_business_account", "entry": [{"changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp", "metadata": {"phone_number_id": "PNID"},
        "messages": [{"id": mid, "from": "5511999990000", "timestamp": "1", **m}]}}]}]}


def test_verify_echoes_challenge_only_with_the_right_token():
    assert meta.verify({"hub.mode": "subscribe", "hub.verify_token": "vt", "hub.challenge": "42"}) == "42"
    assert meta.verify({"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "42"}) is None


def test_signature():
    body = b'{"a":1}'
    good = "sha256=" + hmac.new(b"sekret", body, hashlib.sha256).hexdigest()
    assert meta.signature_ok(body, good)
    assert not meta.signature_ok(body, "sha256=" + "0" * 64) and not meta.signature_ok(body, "")


def test_to_forms_text_audio_and_ignores_statuses_and_retries():
    text = meta.to_forms(_msg("w1", type="text", text={"body": "oi"}))
    assert text == [{"From": "meta:5511999990000", "Body": "oi", "NumMedia": "0"}]
    audio = meta.to_forms(_msg("w2", type="audio", audio={"id": "M1", "mime_type": "audio/ogg; codecs=opus", "voice": True}))
    assert audio[0]["MetaMediaId"] == "M1" and audio[0]["MediaContentType0"] == "audio/ogg"
    assert meta.to_forms(_msg("w1", type="text", text={"body": "oi"})) == []  # Meta retried: handled once
    statuses = {"entry": [{"changes": [{"value": {"statuses": [{"id": "x", "status": "read"}]}}]}]}
    assert meta.to_forms(statuses) == []


def test_download_is_two_authorized_steps():
    calls = []

    def get(url, headers=None, **kw):
        calls.append((url, headers))
        if url.endswith("/M1"):
            return NS(status_code=200, json=lambda: {"url": "https://lookaside/abc"})
        return NS(status_code=200, content=b"OggS")
    assert meta.download("M1", get=get) == b"OggS"
    assert all(h == {"Authorization": "Bearer tok"} for _, h in calls) and calls[1][0] == "https://lookaside/abc"


class FakePost:
    def __init__(self):
        self.calls = []

    def __call__(self, url, headers=None, json=None, data=None, files=None, **kw):
        self.calls.append({"url": url, "json": json, "data": data, "files": files})
        body = {"id": f"MEDIA{len(self.calls)}"} if url.endswith("/media") else {"messages": [{"id": "wamid"}]}
        return NS(status_code=200, json=lambda: body, headers={"content-type": "application/json"})


def test_send_text_voice_note_and_pdf():
    p = FakePost()
    meta.send("meta:5511", "Olá", None, post=p)
    assert p.calls[0]["json"]["type"] == "text" and p.calls[0]["json"]["to"] == "5511"
    p = FakePost()
    meta.send("meta:5511", "", (b"OggS", "resposta_1.ogg"), post=p)
    assert p.calls[0]["url"].endswith("/PNID/media")
    assert p.calls[1]["json"]["audio"] == {"id": "MEDIA1", "voice": True}  # a real voice-note bubble
    p = FakePost()
    meta.send("meta:5511", "Aqui está seu resumo", (b"%PDF", "resumo_ab.pdf"), post=p)
    doc = p.calls[1]["json"]["document"]
    assert doc["filename"] == "resumo.pdf" and doc["caption"] == "Aqui está seu resumo"


def test_send_failure_raises_without_her_words():
    def bad(url, **kw):
        return NS(status_code=400, headers={"content-type": "application/json"},
                  json=lambda: {"error": {"code": 131030, "type": "OAuthException", "message": "Joana"}})
    with pytest.raises(RuntimeError) as e:
        meta.send("meta:5511", "Joana disse", None, post=bad)
    assert "131030" in str(e.value) and "Joana" not in str(e.value)


def test_uploaded_media_is_deleted_later():
    meta._UPLOADED.clear()
    meta._UPLOADED.extend([("old", 0.0), ("new", 990.0)])
    deleted = []
    assert meta.cleanup_uploads(now=1000.0, delete=deleted.append) == 1 and deleted == ["old"]
    assert [m for m, _ in meta._UPLOADED] == ["new"]


def test_webhook_end_to_end(monkeypatch):
    """Signed Meta POST → the real handler → onboarding reply sent through Meta."""
    from fastapi.testclient import TestClient
    monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)
    monkeypatch.delenv("DRY_RUN", raising=False)
    sent = []
    monkeypatch.setattr(meta, "send", lambda to, body="", media=None, post=None: sent.append((to, body)))
    body = json.dumps(_msg(f"w-{os.urandom(3).hex()}", type="text", text={"body": "oi"})).encode()
    sig = "sha256=" + hmac.new(b"sekret", body, hashlib.sha256).hexdigest()
    c = TestClient(app.app)
    assert c.post("/meta", content=body, headers={"X-Hub-Signature-256": "sha256=bad"}).status_code == 403
    assert c.post("/meta", content=body, headers={"X-Hub-Signature-256": sig}).status_code == 200
    assert sent and sent[0][0] == "meta:5511999990000" and "Como você prefere conversar" in sent[0][1]
    assert c.get("/meta", params={"hub.mode": "subscribe", "hub.verify_token": "vt", "hub.challenge": "7"}).text == "7"
    store.delete(store.user_id("meta:5511999990000"))


def test_media_bytes_reads_our_encrypted_file():
    uid = store.user_id("meta:test-media")
    store.write_media(uid, "resumo_x.pdf", b"%PDF-1")
    assert app._media_bytes(app.media_url(uid, "resumo_x.pdf")) == (b"%PDF-1", "resumo_x.pdf")
    store.delete(uid)
