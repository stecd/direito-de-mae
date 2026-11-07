"""ElevenLabs keeps the text of every voice reply in our account history. Personal replies
must be deleted from it; fixed messages (no personal data, cached in public/voice/) may stay."""
import logging
import os
from types import SimpleNamespace as NS

os.environ.setdefault("ANTHROPIC_API_KEY", "test")

import pytest  # noqa: E402

import app  # noqa: E402
import voice  # noqa: E402


@pytest.fixture(autouse=True)
def inline_forget(monkeypatch):
    monkeypatch.setattr(app, "FORGET_IN_BACKGROUND", False)


class FakeHistory:
    def __init__(self, texts, page=20):
        self.items = [NS(history_item_id=f"h{i}", text=t) for i, t in enumerate(texts)]
        self.deleted, self.calls, self.page = [], [], page

    def list(self, **kw):
        self.calls.append(kw)
        start = 0
        if kw.get("start_after_history_item_id"):
            start = [i.history_item_id for i in self.items].index(kw["start_after_history_item_id"]) + 1
        chunk = self.items[start:start + self.page]
        return NS(history=chunk, has_more=start + self.page < len(self.items))

    def delete(self, hid):
        self.deleted.append(hid)
        self.items = [i for i in self.items if i.history_item_id != hid]


def test_forget_deletes_only_that_text():
    h = FakeHistory(["Sua patroa disse X", "Oi! Eu sou o Direito de Mãe", "Sua patroa disse X"])
    assert voice.forget("Sua patroa disse X", voice_id="v", history=h) == 2
    assert [i.text for i in h.items] == ["Oi! Eu sou o Direito de Mãe"]
    assert h.calls[0]["voice_id"] == "v" and h.calls[0]["sort_direction"] == "desc"


def test_forget_pages_back_when_the_reply_is_not_in_the_newest_20():
    h = FakeHistory([f"outra {i}" for i in range(25)] + ["minha resposta"])
    assert voice.forget("minha resposta", voice_id="v", history=h) == 1
    assert len(h.calls) == 2 and h.calls[1]["start_after_history_item_id"] == "h19"


def test_reply_is_forgotten_even_when_speak_fails_after_elevenlabs_logged_it(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "VOICE_CACHE", tmp_path)
    forgotten = []
    monkeypatch.setattr(app.voice, "forget", lambda text: forgotten.append(text) or 1)

    def ffmpeg_crash(text, out):
        raise RuntimeError("ffmpeg failed")
    monkeypatch.setattr(app.voice, "speak", ffmpeg_crash)
    with pytest.raises(RuntimeError):
        app.spoken("Anotei: a patroa disse que vai te demitir")
    assert forgotten == ["Anotei: a patroa disse que vai te demitir"]


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
