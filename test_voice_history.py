"""ElevenLabs keeps the text of every voice reply in our account history. Personal replies
must be deleted from it; fixed messages (no personal data, cached in public/voice/) may stay."""
import logging
import os
from types import SimpleNamespace as NS

os.environ.setdefault("ANTHROPIC_API_KEY", "test")

import app  # noqa: E402
import voice  # noqa: E402


class FakeHistory:
    def __init__(self, texts):
        self.items = [NS(history_item_id=f"h{i}", text=t) for i, t in enumerate(texts)]
        self.deleted = []

    def list(self, **kw):
        return NS(history=list(self.items))

    def delete(self, hid):
        self.deleted.append(hid)
        self.items = [i for i in self.items if i.history_item_id != hid]


def test_forget_deletes_only_that_text():
    h = FakeHistory(["Sua patroa disse X", "Oi! Eu sou o Direito de Mãe", "Sua patroa disse X"])
    assert voice.forget("Sua patroa disse X", voice_id="v", history=h) == 2
    assert [i.text for i in h.items] == ["Oi! Eu sou o Direito de Mãe"]


def _fake_speak(text, out):
    out.write_bytes(b"ogg")
    out.with_suffix(".mp3").write_bytes(b"mp3")
    return out


def test_personal_reply_is_forgotten_fixed_message_is_not(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "VOICE_CACHE", tmp_path)
    monkeypatch.setattr(app.voice, "speak", _fake_speak)
    forgotten = []
    monkeypatch.setattr(app.voice, "forget", lambda text: forgotten.append(text) or 1)
    app.spoken("Anotei: a patroa Joana gritou com você.")
    app.spoken(app.ob.SAFETY_TIP)
    assert forgotten == ["Anotei: a patroa Joana gritou com você."]


def test_failed_deletion_is_logged_without_her_words_and_reply_still_sent(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(app, "VOICE_CACHE", tmp_path)
    monkeypatch.setattr(app.voice, "speak", _fake_speak)

    def boom(text):
        raise PermissionError(f"missing permission for {text}")
    monkeypatch.setattr(app.voice, "forget", boom)
    with caplog.at_level(logging.ERROR):
        assert app.spoken("Joana disse que vai te demitir") == (b"ogg", b"mp3")
    assert "could not delete" in caplog.text and "Joana" not in caplog.text


def test_reply_missing_from_history_is_reported(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(app, "VOICE_CACHE", tmp_path)
    monkeypatch.setattr(app.voice, "speak", _fake_speak)
    monkeypatch.setattr(app.voice, "forget", lambda text: 0)
    with caplog.at_level(logging.ERROR):
        app.spoken("uma resposta pessoal")
    assert "not found in ElevenLabs history" in caplog.text
