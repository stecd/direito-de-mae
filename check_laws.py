"""Watches the laws in laws.md for changes. Run weekly (see .github/workflows/check-laws.yml).

Why this design:
- planalto.gov.br blocks automated requests, so we read the Senado's official index
  (legis.senado.leg.br/norma/<id>). Each index page lists every act that altered the law
  (new laws, MPs, STF decisions). A new entry there is the most direct "this law changed" signal.
- We also fingerprint the text of each article laws.md relies on, from the compiled text,
  so a change the index misses still shows up.
- The DOU (Diário Oficial) is searched as a third, best-effort signal: it is where a change
  is published first and the binding version. Its site drops automated connections often,
  so a DOU failure is reported but never fails the run.

Nothing here edits laws.md. A person reads the report, checks the new text and updates
laws.md by hand; a wrong legal claim reaching a mother is worse than a stale one.

  python check_laws.py            # compare with laws_baseline.json, write laws_status.json
  python check_laws.py --accept   # after updating laws.md: record the current state as baseline
Exit codes: 0 nothing new · 2 something for a person to review · 3 baseline refused (sources unreadable).
"""
import hashlib
import html
import json
import re
import sys
import unicodedata
from datetime import date, timedelta
from pathlib import Path

import httpx

ROOT = Path(__file__).parent
SOURCES = json.loads((ROOT / "laws_sources.json").read_text())
BASELINE = ROOT / "laws_baseline.json"
STATUS = ROOT / "laws_status.json"
UA = "DireitoDeMae-lawcheck/1.0 (+https://github.com/stecd/direito-de-mae)"
DOU_SEARCH = "https://www.in.gov.br/consulta/-/buscar/dou"

# An amending act as the Senado index names it, e.g. "Lei nº 15.371 de 31/03/2026".
ACT = re.compile(r"(Lei Complementar|Lei|Medida Provis[óo]ria|Emenda Constitucional|Decreto-Lei|Decreto|"
                 r"Ac[óo]rd[ãa]o da ADI|ADI|ADC|ADPF)\s+n?[ºo°]?\s*([\d.]+)\s*(?:,?\s*de\s*(\d{1,2}/\d{1,2}/\d{4}))?",
                 re.I)


def text_of(page: str) -> str:
    """HTML to plain, normalized text."""
    page = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", page)
    page = re.sub(r"(?s)<[^>]+>", " ", page)
    page = unicodedata.normalize("NFC", html.unescape(page))
    return re.sub(r"\s+", " ", page).strip()


def acts(index_text: str) -> list[str]:
    """Distinct amending acts named on a Senado index page, normalized."""
    found = set()
    for kind, num, when in ACT.findall(index_text):
        kind = unicodedata.normalize("NFKD", kind).encode("ascii", "ignore").decode().title()
        found.add(f"{kind} {num.replace('.', '')}" + (f" de {when}" if when else ""))
    return sorted(found)


def article(text: str, art: str) -> str | None:
    """The text of one article ("392", "392-A", "71-B", "10"), up to the next article heading.
    Takes the LAST occurrence, so a table of contents or an amending law quoted earlier
    on the page doesn't shadow the article itself."""
    num, _, suffix = art.partition("-")
    sfx = rf"(?:º|°|o)?-{suffix}" if suffix else r"(?:º|°|o)?"  # "1º-A" and "392-A" both occur
    head = re.compile(rf"Art\. ?{num}{sfx}\.? ")
    hits = list(head.finditer(text))
    if not hits:
        return None
    start = hits[-1].start()
    nxt = re.compile(r"Art\. ?\d+(?:º|°|o)?(?:-[A-Z])?\.? ").search(text, hits[-1].end())
    return text[start: nxt.start() if nxt else start + 6000]


def fingerprint(s: str) -> str:
    # Ignore link targets, case and spacing so a site redesign doesn't look like a law change.
    s = re.sub(r"\s+", " ", s.lower()).strip()
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def fetch(url: str) -> str:
    r = httpx.get(url, headers={"User-Agent": UA}, follow_redirects=True, timeout=60)
    r.raise_for_status()
    if "Acesso Negado" in r.text[:2000]:
        raise RuntimeError("blocked (Acesso Negado)")
    return r.text


def snapshot(get=fetch) -> dict:
    """Current state of every source: amending acts + per-article fingerprints."""
    snap, errors = {}, []
    for law in SOURCES["laws"]:
        entry = {"acts": None, "articles": {}}
        try:
            entry["acts"] = acts(text_of(get(law["index_url"])))
        except Exception as e:  # noqa: BLE001 - report and keep going
            errors.append(f"{law['name']}: index {law['index_url']}: {e}")
        try:
            body = text_of(get(law["text_url"]))
            for art in law["articles"]:
                a = article(body, art)
                entry["articles"][art] = fingerprint(a) if a else "MISSING"
        except Exception as e:  # noqa: BLE001
            errors.append(f"{law['name']}: text {law['text_url']}: {e}")
        snap[law["name"]] = entry
    return {"laws": snap, "errors": errors}


def dou_mentions(days: int = 8, get=fetch) -> tuple[list[str], list[str]]:
    """Best effort: DOU publications in the last `days` that name one of our laws."""
    hits, errors = [], []
    since = date.today() - timedelta(days=days)
    for law in SOURCES["laws"]:
        for term in law.get("dou_terms", []):
            url = str(httpx.URL(DOU_SEARCH, params={
                "q": f'"{term}"', "s": "todos", "exactDate": "personalizado",
                "publishFrom": f"{since:%d-%m-%Y}", "publishTo": f"{date.today():%d-%m-%Y}"}))
            try:
                page = get(url)
            except Exception as e:  # noqa: BLE001
                errors.append(f"DOU '{term}': {e}")
                continue
            # The search page embeds its results as JSON in this script tag. Not yet confirmed
            # against a live response (in.gov.br dropped every connection while this was built);
            # if the markup differs, this finds nothing and the Senado checks still run.
            try:
                m = re.search(r'id="_br_com_seatecnologia_in_buscadou_BuscaDouPortlet_params"[^>]*>(.*?)</script>',
                              page, re.S)
                items = json.loads(m.group(1)).get("jsonArray", []) if m else []
            except (ValueError, AttributeError) as e:
                errors.append(f"DOU '{term}': unexpected page format: {e}")
                continue
            for it in items:
                hits.append(f"{it.get('pubDate', '?')} | {it.get('title', '?')} | https://www.in.gov.br/web/dou/-/{it.get('urlTitle', '')}")
    return sorted(set(hits)), errors


# Only these mean the law itself moved. "Not found" usually means the site's layout changed,
# and DOU mentions of "licença-maternidade" are common; both go to the issue, not to mothers.
LAW_CHANGE_MARKERS = ("NEW amending act", "text changed")


def law_changes(changes: list[str]) -> list[str]:
    return [c for c in changes if any(k in c for k in LAW_CHANGE_MARKERS)]


def compare(base: dict, now: dict) -> list[str]:
    """Human-readable list of what changed since the baseline."""
    changes = []
    for name, cur in now["laws"].items():
        old = base.get("laws", {}).get(name)
        if not old:
            changes.append(f"{name}: not in baseline yet")
            continue
        if cur["acts"] is not None and old.get("acts") is not None:
            for a in sorted(set(cur["acts"]) - set(old["acts"])):
                changes.append(f"{name}: NEW amending act listed by the Senado: {a}")
        for art, fp in cur["articles"].items():
            was = old.get("articles", {}).get(art)
            if fp == "MISSING":
                changes.append(f"{name}: art. {art} not found in the compiled text (renumbered, revoked, or the page layout moved)")
            elif was and was != fp:
                changes.append(f"{name}: art. {art} text changed")
    return changes


def main(argv: list[str]) -> int:
    now = snapshot()
    if "--accept" in argv:
        if now["errors"] and "--force" not in argv:
            # A baseline with gaps would silently stop watching those laws forever.
            print("Not recording a baseline: some sources could not be read. Retry later, or pass --force.")
            for e in now["errors"]:
                print("  !", e)
            return 3
        BASELINE.write_text(json.dumps({"accepted": date.today().isoformat(), **now}, ensure_ascii=False, indent=1))
        print(f"Baseline recorded ({len(now['errors'])} fetch errors).")
        for e in now["errors"]:
            print("  !", e)
        return 0
    base = json.loads(BASELINE.read_text()) if BASELINE.exists() else {}
    changes = compare(base, now)
    dou, dou_err = dou_mentions()
    status = {"checked": date.today().isoformat(), "baseline": base.get("accepted"), "changes": changes,
              "law_changes": law_changes(changes), "dou_mentions": dou, "errors": now["errors"] + dou_err}
    # Rewrite the file only when something other than the date moved, so a quiet week is no commit.
    old = json.loads(STATUS.read_text()) if STATUS.exists() else {}
    if {k: v for k, v in old.items() if k != "checked"} != {k: v for k, v in status.items() if k != "checked"}:
        STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=1))
    report = ["# Law check " + status["checked"], f"Baseline accepted: {status['baseline'] or 'none'}", ""]
    report += ["## Changes since baseline"] + ([f"- {c}" for c in changes] or ["- none"])
    report += ["", "## DOU publications naming these laws (last 8 days)"] + ([f"- {d}" for d in dou] or ["- none found"])
    report += ["", "## Fetch errors (not law changes)"] + ([f"- {e}" for e in status["errors"]] or ["- none"])
    print("\n".join(report))
    return 2 if changes or dou else 0  # 2 = something for a person to look at; 1 = the script crashed


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
