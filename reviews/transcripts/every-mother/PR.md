## Every Mother, Every Article

Stacked on #1 (review/plan-around). Merge #1 first.

### What changed
- **laws.md checked against official text.** Every article was fetched verbatim from the Senado (legis.senado.leg.br) and Câmara (CLT) official compilations; planalto.gov.br blocks every automated request, including a real Chrome session. Recent amending laws (15.156/2025, 15.222/2025, 15.371/2026, 15.415/2026) were read in their original published text as the cross-check.
- **Corrections:** CF art. 7º has no parágrafo único; the domestic workers' provision is §1º. Removed "vale mesmo que a patroa não soubesse" and "reintegração ou indenização" (no article supports them in the texts read); discriminatory dismissal now cites Lei 9.029 art. 4º.
- **Expanded to every kind of work:** CLT, doméstica, sem carteira, diarista ≤2 dias, autônoma/contribuinte individual, desempregada, rural, servidora federal; plus Empresa Cidadã, adoption, death of the mother, hospital stays, Zika, consultations, hazardous work (ADI 5.938), miscarriage, breastfeeding, nurseries, discrimination, Emprega + Mulheres, and paternity leave from 01/01/2027.
- **Bot:** asks the kind of work before giving deadlines; returns `work_type`, stored in the profile. Date tags: estabilidade only for CLT/doméstica; leave window for CLT/doméstica/INSS, not for servidora (starts in the 9th month).
- **Dossiê:** rights section per work type; no estabilidade box for servidora.
- **Weekly law check:** `check_laws.py` + `.github/workflows/check-laws.yml`. Signals: new amending acts on each law's Senado index page, per-article fingerprints of the compiled text, and DOU search (best effort). Opens/updates a `law-change` issue; writes `laws_status.json`; while a change is unreviewed, `brain.law_warning()` tells the model to add one sentence that the law may have changed. Never edits laws.md.
- **README:** new section documenting sources, the check, the corrections, open questions and the update mechanism.

### What did not change
Date math, storage, commands, voice, webhook. ADI 7.495 (Senado index note) is not relied on until the STF text is read. State/municipal servants not covered.

### Verification
`.venv/bin/python -m pytest -q test_offline.py` → 18 passed (4 new: dossiê per work type, law warning, index/article parsing incl. "1º-A" headings, change/outage detection). The checker has NOT run against the live sites (build sandbox has no direct network); the DOU result-JSON markup is unconfirmed. Not run live against Claude.
