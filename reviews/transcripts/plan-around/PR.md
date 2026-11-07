## The Dates She Can Plan Around

Three items from the Stretch list in PLAN.md.

### What changed
- **Licença-maternidade dates, computed in code.** `brain.leave_window(due)` returns (earliest start, end): start = due − 28 days, end = due + 119 days (120 days counting the birth day). The model writes `[DATAS_LICENCA]`; `fill_date` replaces it, the same way `[DATA_ESTABILIDADE]` already worked. Legal basis added to `laws.md`: LC 150 art. 25 ("nos termos da CLT") + CLT art. 392 §1º.
- **Missing due date → ask once.** If a reply contains either date tag and no due date is known, the tags become the rule in words and the reply ends with "Quando o nenê deve nascer? Me diga a data e eu calculo seus prazos." Replies with no tag are left alone.
- **Evidence images in the dossiê.** Entries with an image file (jpg/png/gif/webp) present in the user's media folder are shown in a 3-per-row grid labelled "Registro #n", matching the timeline numbering. Missing or unreadable files are skipped. The rights box also shows the leave window.

### What did not change
- The model still never writes a date. Estabilidade math is untouched.
- Letter to patroa: deliberately not built (it alerts the employer; needs an owner + sindicato decision). Noted in PLAN.md.
- No storage, command or webhook changes.

### Verification
`.venv/bin/python -m pytest -q test_offline.py` → 12 passed (3 new: leave window + tag fill, ask-once, PDF embeds an image and skips a missing file). Not run live against Claude/Twilio.
