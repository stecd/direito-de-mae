"""Phase 2 checks (no API keys, no Twilio messages): encryption, retention,
signed links, Twilio cleanup, log scrubbing, onboarding and commands."""
import logging
import os
import time
from urllib.parse import parse_qs, urlparse

os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.update(TWILIO_ACCOUNT_SID="x", TWILIO_AUTH_TOKEN="x", PUBLIC_URL="https://x")

import app  # noqa: E402
import store  # noqa: E402
from onboarding import AUDIO, BOTH, CONSENT_Q, MODE_Q, SAFETY_TIP, TEXT, is_no, is_yes, parse_mode  # noqa: E402


# ---------- Storage ----------

def test_store_files_are_encrypted_and_shredded():
    uid = store.user_id("whatsapp:+5511888888888")
    store.save(uid, {"history": [], "entries": [{"summary": "patroa gritou"}], "profile": {}})
    store.write_media(uid, "prova_x.jpg", b"segredo-da-foto")
    assert b"patroa" not in (store.DATA_DIR / f"{uid}.json").read_bytes()
    assert b"segredo" not in (store.DATA_DIR / uid / "prova_x.jpg").read_bytes()
    assert store.read_media(uid, "prova_x.jpg") == b"segredo-da-foto"
    # A backup copy taken before deletion is unreadable afterwards: the key is gone.
    backup = (store.DATA_DIR / f"{uid}.json").read_bytes()
    store.delete(uid)
    (store.DATA_DIR / f"{uid}.json").write_bytes(backup)
    assert store.load(uid)["entries"] == []
    store.delete(uid)


def test_read_media_refuses_path_traversal():
    assert store.read_media("..", "store.py") is None
    assert store.read_media("abc", "../../store.py") is None


def test_legacy_plaintext_file_still_loads_then_saves_encrypted():
    uid = store.user_id("whatsapp:+5511777777777")
    (store.DATA_DIR / f"{uid}.json").write_text('{"history": [], "entries": [{"a": 1}], "profile": {}}')
    u = store.load(uid)
    assert u["entries"] == [{"a": 1}]
    store.save(uid, u)
    assert not (store.DATA_DIR / f"{uid}.json").read_bytes().startswith(b"{")
    store.delete(uid)


def test_sweep_deletes_only_expired_users():
    old, saved = store.user_id("whatsapp:+551191"), store.user_id("whatsapp:+551193")
    for uid in (old, saved):
        store.save(uid, {"history": [], "entries": [], "profile": {}})
    u = store.load(saved)
    u["profile"]["keep_days"] = store.SAVED_KEEP_DAYS
    store.save(saved, u)
    assert old not in store.sweep(now=time.time() + 80 * store.DAY)  # 80 quiet days: kept
    gone = store.sweep(now=time.time() + 100 * store.DAY)            # 100 quiet days: deleted
    assert old in gone and saved not in gone
    assert not store.exists(old) and store.exists(saved)
    store.delete(saved)


# ---------- Links, Twilio, logs ----------

def test_signed_media_links_expire_and_cant_be_forged():
    url = app.media_url("u1", "resumo_a.pdf", now=1000)
    q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
    assert app.link_ok("u1", "resumo_a.pdf", q["exp"], q["sig"], now=1000)
    assert not app.link_ok("u1", "resumo_a.pdf", q["exp"], q["sig"], now=1000 + 16 * 60)  # expired
    assert not app.link_ok("u2", "resumo_a.pdf", q["exp"], q["sig"], now=1000)  # other user
    assert not app.link_ok("u1", "prova_b.jpg", q["exp"], q["sig"], now=1000)  # other file
    assert not app.link_ok("u1", "resumo_a.pdf", str(int(q["exp"]) + 9999), q["sig"], now=1000)  # stretched
    assert not app.link_ok("u1", "resumo_a.pdf", "x", "y")


def test_media_endpoint_rejects_unsigned_links():
    from fastapi.testclient import TestClient
    uid = store.user_id("whatsapp:+551194")
    store.write_media(uid, "resumo_t.pdf", b"%PDF-1.4 x")
    c = TestClient(app.app)
    assert c.get(f"/media/{uid}/resumo_t.pdf").status_code == 404
    good = app.media_url(uid, "resumo_t.pdf").replace("https://x", "")
    r = c.get(good)
    assert r.status_code == 200 and r.content == b"%PDF-1.4 x"
    store.delete(uid)


def test_twilio_cleanup_deletes_after_delivery_and_retries(monkeypatch):
    monkeypatch.setattr(app, "CLEANUP_FILE", store.DATA_DIR / "_test_cleanup.json")
    app.CLEANUP_FILE.unlink(missing_ok=True)
    deleted, failing = [], {"SMbad"}

    class Client:
        def messages(self, sid):
            class Msg:
                def delete(_):
                    if sid in failing:
                        raise RuntimeError("still sending")
                    deleted.append(sid)
            return Msg()

    app._queue_cleanup("SMgood")
    app._queue_cleanup("SMbad")
    assert app.twilio_cleanup(now=time.time(), client=Client()) == 0  # too soon: still delivering
    assert app.twilio_cleanup(now=time.time() + 300, client=Client()) == 1
    assert deleted == ["SMgood"] and [i["sid"] for i in app._load_cleanup()] == ["SMbad"]
    for _ in range(6):
        app.twilio_cleanup(now=time.time() + 300, client=Client())
    assert app._load_cleanup() == []  # gives up after 6 tries instead of growing forever
    app.CLEANUP_FILE.unlink(missing_ok=True)


# ---------- Onboarding words ----------

def test_parse_mode_from_her_own_words():
    assert parse_mode("1") == TEXT and parse_mode("2") == AUDIO and parse_mode("3") == BOTH
    assert parse_mode("prefiro mensagem escrita") == TEXT
    assert parse_mode("Áudio, por favor") == AUDIO
    assert parse_mode("mensagem de voz") == AUDIO
    assert parse_mode("os dois") == BOTH and parse_mode("texto e áudio") == BOTH
    assert parse_mode("oi tudo bem", spoken=True) == AUDIO  # she answered with a voice note
    assert parse_mode("oi tudo bem") is None
    assert parse_mode("quero trocar minha escolha") is None  # re-ask, don't guess


def test_yes_no():
    assert is_yes("SIM") and is_yes("sim, pode") and is_yes("Ok")
    assert is_no("Não") and is_no("nao quero") and not is_yes("não")
    assert not is_yes("") and not is_no("")


def test_keywords_skip_ai():
    k = lambda t: app.keyword(app.command(t), False)  # noqa: E731
    assert k("Apagar") == "apagar" and k("salvar!") == "salvar" and k("Meus dados") == "meus_dados"
    assert k("mudar") == "mudar_modo" and k("Dossiê") == "resumo" and k("resumo") == "resumo"
    assert k("quero trocar minha escolha") is None  # goes to Claude, which reads the intent


# ---------- The real handler, with Claude and voice stubbed ----------

class Bot:
    def __init__(self, monkeypatch, brain_out=None):
        self.sent, self.calls = [], []
        self.brain_out = brain_out or {"reply": "Resposta da IA."}
        monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)
        monkeypatch.setattr(app, "send", lambda to, body="", media=None: self.sent.append((body, media)))
        monkeypatch.setattr(app.brain, "think",
                            lambda h, c, e=None: (self.calls.append(c), dict(self.brain_out))[1])
        self.phone = f"web:test-{os.urandom(4).hex()}"
        self.uid = store.user_id(self.phone)

    def msg(self, text):
        self.sent.clear()
        app._handle({"From": self.phone, "Body": text, "NumMedia": "0"})
        return " ".join(b for b, _ in self.sent)

    def user(self):
        return store.load(self.uid)


def onboarded(monkeypatch, brain_out=None):
    bot = Bot(monkeypatch, brain_out)
    bot.msg("oi")
    bot.msg("1")
    bot.msg("sim")
    bot.calls.clear()
    return bot


def test_onboarding_full_interview(monkeypatch):
    bot = Bot(monkeypatch)
    out = bot.msg("Sou babá e estou grávida, a patroa quer me mandar embora")
    assert MODE_Q in out and not bot.calls  # no AI before she chooses and agrees
    out = bot.msg("prefiro mensagem escrita")
    assert CONSENT_Q in out and bot.user()["profile"]["mode"] == "text"
    out = bot.msg("o que você faz com isso?")
    assert "SIM" in out and not bot.calls
    out = bot.msg("Sim")
    assert SAFETY_TIP in out and "Resposta da IA." in out  # her first message is answered now
    assert "babá" in bot.calls[0][0]["text"]
    assert bot.user()["profile"]["onboarding"] == "done"
    store.delete(bot.uid)


def test_onboarding_no_consent_keeps_nothing(monkeypatch):
    bot = Bot(monkeypatch)
    bot.msg("oi")
    bot.msg("3")
    assert "Não guardei nada" in bot.msg("não")
    assert not store.exists(bot.uid)


def test_apagar_needs_confirmation(monkeypatch):
    bot = onboarded(monkeypatch)
    assert "APAGAR de novo" in bot.msg("APAGAR")
    assert store.exists(bot.uid)
    assert "apagados" in bot.msg("apagar")
    assert not store.exists(bot.uid)


def test_apagar_confirmation_is_cancelled_by_another_message(monkeypatch):
    bot = onboarded(monkeypatch)
    bot.msg("APAGAR")
    bot.msg("deixa, me fala da licença")
    assert "APAGAR de novo" in bot.msg("APAGAR")  # asks again: the old request was dropped
    assert store.exists(bot.uid)
    store.delete(bot.uid)


def test_delete_in_her_own_words_still_asks_first(monkeypatch):
    bot = onboarded(monkeypatch, {"reply": "ok", "intent": "apagar"})
    assert "APAGAR de novo" in bot.msg("quero apagar tudo que te mandei")
    assert store.exists(bot.uid)
    store.delete(bot.uid)


def test_change_mode_in_her_own_words(monkeypatch):
    bot = onboarded(monkeypatch, {"reply": "ok", "intent": "mudar_modo"})
    assert "1 para mensagem escrita" in bot.msg("quero trocar minha escolha")
    bot.msg("agora prefiro áudio")
    assert bot.user()["profile"]["mode"] == "audio"
    store.delete(bot.uid)


def test_salvar_extends_retention_and_meus_dados_reports(monkeypatch):
    bot = onboarded(monkeypatch)
    assert "1 ano" in bot.msg("SALVAR")
    assert bot.user()["profile"]["keep_days"] == store.SAVED_KEEP_DAYS
    out = bot.msg("meus dados")
    assert "0 registro" in out and "mensagem escrita" in out
    store.delete(bot.uid)


def test_resumo_pdf_is_encrypted_with_signed_link(monkeypatch):
    import io
    from PIL import Image
    bot = onboarded(monkeypatch)
    buf = io.BytesIO()
    Image.new("RGB", (300, 300), "white").save(buf, "JPEG")
    u = bot.user()
    u["entries"].append({"summary": "print", "file": store.write_media(bot.uid, "prova_p.jpg", buf.getvalue())})
    store.save(bot.uid, u)
    bot.msg("RESUMO")
    body, link = bot.sent[0]
    assert "resumo" in body and "sig=" in link and "dossi" not in body.lower()
    name = urlparse(link).path.split("/")[-1]
    assert not (store.DATA_DIR / bot.uid / name).read_bytes().startswith(b"%PDF")
    assert store.read_media(bot.uid, name).startswith(b"%PDF")
    store.delete(bot.uid)


def test_reply_mode_is_honoured(monkeypatch):
    bot = onboarded(monkeypatch)
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "v")
    monkeypatch.setenv("VOICE_REPLIES", "1")

    def fake_speak(text, out):
        out.write_bytes(b"ogg")
        out.with_suffix(".mp3").write_bytes(b"mp3")
        return out
    monkeypatch.setattr(app.voice, "speak", fake_speak)
    bot.sent.clear()
    app.say("p", bot.uid, "olá", mode="audio")
    assert len(bot.sent) == 1 and bot.sent[0][0] == "" and ".ogg" in bot.sent[0][1]
    bot.sent.clear()
    app.say("p", bot.uid, "olá", mode="text")
    assert bot.sent == [("olá", None)]
    bot.sent.clear()
    app.say("p", bot.uid, "olá", mode="both")
    assert bot.sent[0] == ("olá", None) and ".ogg" in bot.sent[1][1]
    store.delete(bot.uid)


def test_logs_never_contain_message_text(monkeypatch, caplog):
    bot = onboarded(monkeypatch)
    with caplog.at_level(logging.DEBUG):
        bot.msg("a patroa Joana disse que vai me demitir")
    assert "Joana" not in caplog.text
    store.delete(bot.uid)


def test_voice_replies_off_by_default(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "v")
    monkeypatch.delenv("VOICE_REPLIES", raising=False)
    assert not app.voice_on()
    monkeypatch.setenv("VOICE_REPLIES", "1")
    assert app.voice_on()


def test_fixed_messages_are_voiced_once_then_cached(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "VOICE_CACHE", tmp_path / "cache")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "v")
    calls = []

    def fake_speak(text, out):
        calls.append(text)
        out.write_bytes(b"ogg")
        out.with_suffix(".mp3").write_bytes(b"mp3")
        return out
    monkeypatch.setattr(app.voice, "speak", fake_speak)
    fixed = app.ob.WELCOME + "\n\n" + app.ob.MODE_Q
    assert app.spoken(fixed) == (b"ogg", b"mp3")
    assert app.spoken(fixed) == (b"ogg", b"mp3")
    assert calls == [fixed]  # second time came from the cache
    app.spoken("Sua patroa disse algo pessoal")
    app.spoken("Sua patroa disse algo pessoal")
    assert len(calls) == 3  # personal replies are never cached
    assert len(list((tmp_path / "cache").iterdir())) == 2  # only the fixed message's ogg + mp3
