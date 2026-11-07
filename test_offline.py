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


def test_spoken_resumo_matching():
    from app import wants_resumo
    assert wants_resumo("QUEROMEUDOCE", spoken=True)
    assert not wants_resumo("QUEROMEUDOCE", spoken=False)
    assert not wants_resumo("GOSTODEDOCE", spoken=True)
    assert wants_resumo("DOSSIE", spoken=False) and wants_resumo("RESUMO", spoken=False)
    assert wants_resumo("MANDAMEURELATORIO", spoken=False)


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


def test_leave_tag_alone_still_asks():
    out = fill_date("Sua licença: [DATAS_LICENCA].", None)
    assert ASK_DUE in out and "28 dias" in out and "[" not in out


def test_pdf_skips_corrupt_image_and_wraps_rows(tmp_path: Path):
    from PIL import Image
    for n in range(4):
        Image.new("RGB", (3000, 4000), "white").save(tmp_path / f"p{n}.jpg")
    (tmp_path / "broken.jpg").write_bytes(b"not an image")
    entries = [{"summary": str(n), "file": f"p{n}.jpg"} for n in range(4)] + [{"summary": "x", "file": "broken.jpg"}]
    out = dossie.build({"profile": {}, "entries": entries}, tmp_path / "d.pdf")
    assert out.stat().st_size < 2_000_000  # photos were downscaled


def test_dossie_rights_follow_work_type(tmp_path: Path):
    for wt in ("clt", "domestica", "servidora", "autonoma", "desempregada", "rural", None, "bogus"):
        user = {"profile": {"due_date": "2027-01-20", "work_type": wt}, "entries": []}
        assert dossie.build(user, tmp_path / f"{wt}.pdf").stat().st_size > 1000
    assert all(lead != "Estabilidade da gestante:" for lead, _ in dossie.RIGHTS["servidora"])
    assert any(lead == "Estabilidade da gestante:" for lead, _ in dossie.RIGHTS["domestica"])


def test_law_warning_only_when_unreviewed_change(tmp_path: Path):
    from brain import law_warning
    f = tmp_path / "s.json"
    assert law_warning(f) == ""  # missing file
    f.write_text("not json")
    assert law_warning(f) == ""
    f.write_text('{"checked": "2026-11-09", "changes": [], "dou_mentions": []}')
    assert law_warning(f) == ""
    f.write_text('{"checked": "2026-11-09", "changes": ["CLT: art. 392 not found"], "law_changes": [], '
                 '"dou_mentions": ["x"]}')
    assert law_warning(f) == ""  # layout break or DOU mention alone: no warning to mothers
    f.write_text('{"checked": "2026-11-09", "law_changes": ["CLT: art. 392 text changed"]}')
    assert "pode ter mudado" in law_warning(f)


SENADO_INDEX = """<html><body><h1>Lei nº 11.770</h1><table>
<tr><td>Lei nº 13.257 de 08/03/2016</td><td>Alteração</td></tr>
<tr><td>Medida Provisória nº 1.116 de 04/05/2022</td></tr>
<tr><td>Acórdão da ADI nº 7.495 de 23/09/2026</td></tr></table></body></html>"""

COMPILED = ("<p>Art. 1º É instituído o Programa.</p><p>I - por 60 dias</p>"
            "<p>Art. 1º-A. Fica a empresa autorizada.</p><p>Art. 2º É a administração.</p>"
            "<p>Art. 10. Dez.</p>")


def test_check_laws_parses_index_and_articles():
    import check_laws as cl
    a = cl.acts(cl.text_of(SENADO_INDEX))
    assert "Lei 13257 de 08/03/2016" in a and "Medida Provisoria 1116 de 04/05/2022" in a
    assert any(x.startswith("Acordao Da Adi 7495") for x in a)
    t = cl.text_of(COMPILED)
    assert cl.article(t, "1").startswith("Art. 1º É instituído") and "1º-A" not in cl.article(t, "1")
    assert cl.article(t, "1-A").startswith("Art. 1º-A")
    assert cl.article(t, "10").startswith("Art. 10.") and cl.article(t, "11") is None


def test_check_laws_detects_new_act_changed_and_missing_article(monkeypatch):
    import check_laws as cl
    pages = {}
    for law in cl.SOURCES["laws"]:
        pages[law["index_url"]] = SENADO_INDEX
        pages[law["text_url"]] = COMPILED
    base = cl.snapshot(get=pages.__getitem__)
    assert not [c for c in cl.compare(base, base) if "changed" in c or "NEW" in c]
    changed = dict(pages)
    law = cl.SOURCES["laws"][5]  # Lei 11.770
    changed[law["index_url"]] = SENADO_INDEX.replace("</table>", "<tr><td>Lei nº 15.999 de 01/02/2027</td></tr></table>")
    changed[law["text_url"]] = COMPILED.replace("por 60 dias", "por 90 dias")
    out = cl.compare(base, cl.snapshot(get=changed.__getitem__))
    assert any("NEW amending act" in c and "15999" in c for c in out)
    assert any("art. 1 text changed" in c for c in out)

    def down(url):
        raise RuntimeError("socket hang up")
    snap = cl.snapshot(get=down)
    assert len(snap["errors"]) == 2 * len(cl.SOURCES["laws"])
    assert not [c for c in cl.compare(base, snap) if "changed" in c or "NEW" in c]  # outage is not a law change


def test_check_laws_dou_bad_markup_is_an_error_not_a_crash():
    import check_laws as cl
    page = '<script id="_br_com_seatecnologia_in_buscadou_BuscaDouPortlet_params">{not json</script>'
    hits, errors = cl.dou_mentions(get=lambda url: page)
    assert hits == [] and errors and "unexpected page format" in errors[0]


def test_check_laws_refuses_baseline_with_gaps(monkeypatch, tmp_path):
    import check_laws as cl
    monkeypatch.setattr(cl, "BASELINE", tmp_path / "b.json")
    monkeypatch.setattr(cl, "snapshot", lambda: {"laws": {}, "errors": ["CLT: text: socket hang up"]})
    assert cl.main(["--accept"]) == 3 and not (tmp_path / "b.json").exists()
