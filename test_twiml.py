"""Immediate-reply mode for trial 'Try out WhatsApp' numbers: the bot answers inside Twilio's
webhook request (TwiML), within TWIML_BUDGET seconds. No network calls here."""
import asyncio
import os
import time
from datetime import datetime, timezone
from types import SimpleNamespace as NS

os.environ.setdefault("ANTHROPIC_API_KEY", "test")

import app  # noqa: E402
import store  # noqa: E402


def test_render_sends_voice_and_drops_parked_text_when_voice_arrived():
    xml = app.render_twiml([{"text": "Olá", "media": None, "fallback": True},
                            {"text": "", "media": "https://x/media/u/r.ogg?exp=1&sig=s"}])
    assert "r.ogg" in xml and "Olá" not in xml


def test_render_keeps_parked_text_when_voice_did_not_arrive():
    xml = app.render_twiml([{"text": "Olá", "media": None, "fallback": True}])
    assert "Olá" in xml


def test_render_escapes_and_keeps_order():
    xml = app.render_twiml([{"text": "A & B <ok>", "media": None}, {"text": "resumo", "media": "https://x/p.pdf"}])
    assert "A &amp; B &lt;ok&gt;" in xml and xml.index("A &amp;") < xml.index("resumo")


def _form(phone, body):
    return {"From": phone, "Body": body, "NumMedia": "0"}


def test_answer_in_time_returns_the_bots_messages(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)
    phone = f"whatsapp:+55119{os.urandom(3).hex()}"
    xml = asyncio.run(app.answer_in_time(_form(phone, "oi")))
    assert "Como você prefere conversar" in xml  # the onboarding question, as TwiML
    store.delete(store.user_id(phone))


def test_slow_reply_still_answers_within_budget(monkeypatch):
    monkeypatch.setattr(app, "TWIML_BUDGET", 0.3)
    monkeypatch.setattr(app, "handle", lambda form: time.sleep(2))
    t = time.time()
    xml = asyncio.run(app.answer_in_time(_form("whatsapp:+1", "oi")))
    assert time.time() - t < 1.5 and "Recebi" in xml  # never leaves Twilio waiting past 15 s


def test_slow_voice_falls_back_to_the_text(monkeypatch):
    """Audio mode: the voice note isn't ready in time, so she gets the text."""
    monkeypatch.setattr(app, "TWIML_BUDGET", 0.5)
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "v")
    monkeypatch.setenv("VOICE_REPLIES", "1")

    def slow_spoken(text):
        time.sleep(2)
        return b"ogg", b"mp3"
    monkeypatch.setattr(app, "spoken", slow_spoken)
    monkeypatch.setattr(app, "handle", lambda form: app.say("whatsapp:+1", "_shared", "Sua licença…", mode="audio"))
    xml = asyncio.run(app.answer_in_time(_form("whatsapp:+1", "x")))
    assert "Sua licença" in xml


def test_fetch_media_retries_without_credentials_and_rejects_error_pages():
    calls = []

    def get(url, auth=None, **kw):
        calls.append(auth)
        if auth:
            return NS(status_code=403, headers={"content-type": "application/json"}, content=b'{"code":20003}')
        return NS(status_code=200, headers={"content-type": "audio/ogg"}, content=b"OggS")
    assert app.fetch_media("https://api.twilio.com/m", get=get) == b"OggS"
    assert calls[0] is not None and calls[1] is None

    def always_html(url, auth=None, **kw):
        return NS(status_code=200, headers={"content-type": "text/html"}, content=b"<html>login</html>")
    assert app.fetch_media("https://x", get=always_html) is None  # an error page is never her audio


def test_sweep_replies_deletes_old_outbound_only():
    now = time.time()
    old = datetime.fromtimestamp(now - 600, tz=timezone.utc)
    new = datetime.fromtimestamp(now - 10, tz=timezone.utc)
    msgs = [NS(sid="A", direction="outbound-reply", date_sent=old),
            NS(sid="B", direction="outbound-reply", date_sent=new),
            NS(sid="C", direction="inbound", date_sent=old)]
    deleted = []

    class Messages:
        def __call__(self, sid):
            return NS(delete=lambda: deleted.append(sid))

        def list(self, limit=100):
            return msgs
    c = NS(messages=Messages())
    assert app.sweep_replies(now=now, client=c) == 1 and deleted == ["A"]
