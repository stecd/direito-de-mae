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
    monkeypatch.setattr(app.voice, "forget_id", lambda hid: forgotten.append(hid))

    def ffmpeg_crash(text, out, on_history_id=None):
        on_history_id("hist-999")  # ElevenLabs answered, then ffmpeg crashed
        raise RuntimeError("ffmpeg failed")
    monkeypatch.setattr(app.voice, "speak", ffmpeg_crash)
    with pytest.raises(RuntimeError):
        app.spoken("Anotei: a patroa disse que vai te demitir")
    assert forgotten == ["hist-999"]  # exactly the item ElevenLabs created


def _fake_speak(text, out, on_history_id=None):
    if on_history_id:
        on_history_id("hist-123")
    out.write_bytes(b"ogg")
    out.with_suffix(".mp3").write_bytes(b"mp3")
    return out


def test_personal_reply_is_forgotten_fixed_message_is_not(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "VOICE_CACHE", tmp_path)
    monkeypatch.setattr(app.voice, "speak", _fake_speak)
    forgotten = []
    monkeypatch.setattr(app.voice, "forget_id", lambda hid: forgotten.append(hid))
    app.spoken("Anotei: a patroa Joana gritou com você.")
    app.spoken(app.ob.SAFETY_TIP)
    assert forgotten == ["hist-123"]  # the personal reply's own item; the fixed one is kept


def test_failed_deletion_is_logged_without_her_words_and_reply_still_sent(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(app, "VOICE_CACHE", tmp_path)
    monkeypatch.setattr(app.voice, "speak", _fake_speak)

    def boom(hid):
        raise PermissionError("missing permission for Joana disse que vai te demitir")
    monkeypatch.setattr(app.voice, "forget_id", boom)
    with caplog.at_level(logging.ERROR):
        assert app.spoken("Joana disse que vai te demitir") == (b"ogg", b"mp3")
    assert "could not delete" in caplog.text and "Joana" not in caplog.text


def test_reply_missing_from_history_is_reported(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(app, "VOICE_CACHE", tmp_path)
    monkeypatch.setattr(app.voice, "speak", lambda text, out, on_history_id=None: _fake_speak(text, out))
    monkeypatch.setattr(app.voice, "forget", lambda text: 0)
    with caplog.at_level(logging.ERROR):
        app.spoken("uma resposta pessoal")
    assert "not found in ElevenLabs history" in caplog.text


def test_ten_mothers_at_once_each_deletes_only_her_own_item(monkeypatch, tmp_path):
    """Delete by id: identical texts or a crowded history can't make one mother's deletion
    hit another's item."""
    import itertools
    monkeypatch.setattr(app, "VOICE_CACHE", tmp_path)
    ids = itertools.count()

    def speak(text, out, on_history_id=None):
        on_history_id(f"item-{next(ids)}")
        return _fake_speak(text, out)
    monkeypatch.setattr(app.voice, "speak", speak)
    deleted = []
    monkeypatch.setattr(app.voice, "forget_id", lambda hid: deleted.append(hid))
    monkeypatch.setattr(app.voice, "forget", lambda text: pytest.fail("text matching must not be used"))
    for _ in range(10):
        app.spoken("Anotei: a patroa disse que vai te mandar embora.")  # same words, ten mothers
    assert deleted == [f"item-{i}" for i in range(10)]  # each exactly once, her own


def test_speak_reports_the_history_id_before_downloading(monkeypatch, tmp_path):
    """The id comes from the response header, before the audio is read."""
    order = []

    class Resp:
        headers = {"history-item-id": "abc"}

        @property
        def data(self):
            order.append("download")
            return iter([b"mp3"])

    class Ctx:
        def __enter__(self):
            return Resp()

        def __exit__(self, *a):
            return False
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "v")
    monkeypatch.setattr(voice.client.text_to_speech.with_raw_response, "convert", lambda **kw: Ctx())
    monkeypatch.setattr(voice.subprocess, "run", lambda *a, **k: (tmp_path / "o.ogg").write_bytes(b"ogg"))
    voice.speak("oi", tmp_path / "o.ogg", on_history_id=lambda hid: order.append(hid))
    assert order == ["abc", "download"]
