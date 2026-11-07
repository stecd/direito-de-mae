"""Offline checks (no API keys needed): dates, commands, PDF, storage."""
import os
from datetime import date
from pathlib import Path

os.environ.setdefault("ANTHROPIC_API_KEY", "test")

from brain import ASK_DUE, _parse, fill_date, job_protection_end, leave_window  # noqa: E402
import dossie  # noqa: E402
import store  # noqa: E402


def test_dates():
    assert job_protection_end(date(2027, 1, 20)) == date(2027, 6, 20)
    assert job_protection_end(date(2026, 9, 30)) == date(2027, 2, 28)  # month-end clamp
    assert job_protection_end(date(2026, 8, 15)) == date(2027, 1, 15)  # year rollover


def test_fill_date():
    assert fill_date("até [DATA_ESTABILIDADE].", "2027-01-20") == "até 20/06/2027."
    assert "5 meses" in fill_date("até [DATA_ESTABILIDADE].", None)


def test_parse_bad_json_falls_back_to_text():
    assert _parse("oi, sem json")["reply"] == "oi, sem json"
    assert _parse('blah {"reply": "x", "entry": null} blah')["reply"] == "x"


def test_command_normalization():
    os.environ.update(TWILIO_ACCOUNT_SID="x", TWILIO_AUTH_TOKEN="x", PUBLIC_URL="https://x")
    from app import command
    assert command("Dossiê.") in ("DOSSIE",)
    assert command("apagar!") == "APAGAR"


def test_pdf_with_tricky_characters(tmp_path: Path):
    user = {"profile": {"due_date": "2027-01-20"}, "entries": [
        {"date_event": "2026-11-12", "source": "print", "who": "patroa",
         "summary": "Disse “vou te mandar embora” — 😡", "article": "LC 150 art. 25", "date_logged": "2026-11-06"}]}
    out = dossie.build(user, tmp_path / "d.pdf")
    assert out.stat().st_size > 1000


def test_store_roundtrip_and_delete():
    uid = store.user_id("whatsapp:+5511999999999")
    assert "5511" not in uid
    store.save(uid, {"history": [], "entries": [{"a": 1}], "profile": {}})
    (store.media_dir(uid) / "x.txt").write_text("x")
    assert store.load(uid)["entries"] == [{"a": 1}]
    store.delete(uid)
    assert not store.exists(uid) and not (store.DATA_DIR / uid).exists()


def test_sid_validation():
    from app import valid_sid
    assert valid_sid("123e4567-e89b-12d3-a456-426614174000")
    assert not valid_sid("short") and not valid_sid("../../etc/passwd!") and not valid_sid(None)


def test_spoken_dossie_matching():
    from app import wants_dossie
    assert wants_dossie("QUEROMEUDOCE", spoken=True)
    assert not wants_dossie("QUEROMEUDOCE", spoken=False)
    assert not wants_dossie("GOSTODEDOCE", spoken=True)
    assert wants_dossie("DOSSIE", spoken=False)


def test_rate_limiter():
    from app import RateLimiter
    rl = RateLimiter(limit=2, window=10)
    assert rl.allow("a", 0) and rl.allow("a", 1) and not rl.allow("a", 2)
    assert rl.allow("b", 2) and rl.allow("a", 11)


def test_leave_window_and_tags():
    assert leave_window(date(2027, 1, 20)) == (date(2026, 12, 23), date(2027, 5, 19))
    out = fill_date("Licença: [DATAS_LICENCA].", "2027-01-20")
    assert "23/12/2026" in out and "19/05/2027" in out and "[" not in out


def test_missing_due_date_asks_once():
    out = fill_date("Até [DATA_ESTABILIDADE]. Licença: [DATAS_LICENCA].", None)
    assert out.count(ASK_DUE) == 1 and "[" not in out
    assert ASK_DUE not in fill_date("Oi, tudo bem?", None)


def test_pdf_embeds_evidence_images(tmp_path: Path):
    from PIL import Image
    Image.new("RGB", (400, 700), "white").save(tmp_path / "prova_1.jpg")
    base = {"profile": {}, "entries": [{"summary": "print", "file": "prova_1.jpg"},
                                       {"summary": "sumiu", "file": "missing.jpg"}]}
    without = dossie.build({**base, "entries": base["entries"][1:]}, tmp_path / "a.pdf").stat().st_size
    with_img = dossie.build(base, tmp_path / "b.pdf").stat().st_size
    assert with_img > without
