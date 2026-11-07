# Direito de Mãe

**A voice-first helper for any working mother in Brazil, built first for pregnant domestic workers.** She talks to it like she talks on WhatsApp, with voice notes, screenshots or text. It tells her which rights she has (only from Brazilian law we curate, always citing the article), keeps a dated record of what her employer does, and turns that record into a **dossiê** PDF she can take to her union or the Defensoria Pública (free public legal aid).

## Why
- Only **8%** of new mothers in Brazil know all 16 of their labour rights, and **54%** had at least one broken ([FAPESP, Feb 2026](https://agencia.fapesp.br/57148)).
- **Domestic workers** (nannies, housekeepers, caregivers) have it worst. Their employer is a family, so there's no HR department and no witnesses, and many work without a signed work card. They still have rights under **LC 150/2015** (the domestic workers law), but they rarely know it. The demo story follows one of them; the law corpus covers every working mother: CLT employees, domestic workers, informal workers, self-employed and MEI, unemployed women, rural workers and federal public servants.
- Many of them don't read well, and none of them will type "quais meus direitos segundo a LC 150" into a chatbot. General assistants answer whatever they're asked. This one asks her about her situation, listens, and organises her evidence.

## How it helps, step by step

| | |
|---|---|
| <img src="docs/chat-1-voice-and-print.png" width="340"> | **1. She just talks.** She sends a voice note: *"I'm a nanny, no work card, 6 months pregnant, due 20 January. My boss says she'll let me go after the baby is born."*<br><br>**2. It answers in plain words, with the law.** Her job is protected until **20/06/2027**. That date is **calculated by code**, never guessed by the AI. The answer cites **LC 150 art. 25** and **ADCT art. 10, II, b**. Every reply is also **read back as a voice note**, so she never has to read.<br><br>**3. Her evidence becomes a record.** She sends a screenshot of the boss's message (*"you didn't come in today, I'll have to let you go"*). It logs the incident (*"Anotei"*), says **"Não sou advogada"** (I'm not a lawyer), and points her to the **domestic workers' union first, then the Defensoria Pública**. It also asks for the date, since a case needs one. |
| <img src="docs/chat-2-dossie.png" width="340"> | **4. One word, by voice or text: "dossiê".** She gets a PDF with everything she's sent, organised.<br><br>She can say it out loud too. Voice commands work even when speech-to-text mishears it (*"quero meu doce"*). |
| <img src="docs/dossie-pdf.png" width="340"> | **5. A document a lawyer can use.** It shows her due date and her job-protection end date, her key rights with articles, a dated timeline (who, what, source, related law, attached file), and where to get free help. It says clearly that it **organises her evidence and is not legal advice**. |

## Trust & safety
- **Grounded:** Claude may only answer from [`laws.md`](laws.md), and must cite the article. If something isn't covered, it says "não sei com certeza" and sends her to human help. To update the law, edit one file.
- **No made-up dates:** tested functions compute the job-protection end and the maternity-leave window from her due date.
- **Checked against official law, and watched for changes:** see the next section.
- **Human handoff, every time a right looks broken:** union → Defensoria → Ministério Público do Trabalho.
- **Private by default:** no name or phone number stored, only a salted hash. Each browser gets its own session, and **APAGAR** deletes all her data and files.
- **Abuse limits:** per-IP rate limit, file size and type checks.

## The law: where it comes from and how it was checked

The bot can only say what is in [`laws.md`](laws.md). So that file has to be right, complete for every kind of working mother, and current. This is how it was built on 06/11/2026.

**1. Sources.** The legally binding text of a Brazilian law is the one published in the *Diário Oficial da União* (DOU). But the DOU prints each law as it came out, so it has the 1943 CLT, then every later law that amended it, each separately. Nobody reads "art. 392 as it is today" from the DOU. Government bodies publish *compiled* texts that apply every amendment. We used the official compilations of the **Senado Federal** (legis.senado.leg.br) and the **Câmara dos Deputados** (camara.leg.br), which are as official as planalto.gov.br. Planalto was tried first and blocks every automated request ("Acesso Negado"), including from a real Chrome session, so it could not be used.

| Law | What it covers here | Official text used |
|---|---|---|
| CF/88 art. 7º, 201 | 120-day leave for all workers; domestic workers' rights (§1º); maternity protection | Senado [579494](https://legis.senado.leg.br/norma/579494/publicacao/16434817) |
| ADCT art. 10 | Job protection until 5 months after birth; father's 5 days | Senado [604119](https://legis.senado.leg.br/norma/604119/publicacao/16434816) |
| CLT arts. 373-A, 389–400, 473 | Leave, job protection, consultations, hazardous work, miscarriage, breastfeeding, nurseries, adoption, discrimination | Câmara [texto atualizado](https://www2.camara.leg.br/legin/fed/declei/1940-1949/decreto-lei-5452-1-maio-1943-415500-normaatualizada-pe.html) |
| LC 150/2015 | Who counts as a domestic worker; her leave and job protection; hours, FGTS, holidays | Senado [572905](https://legis.senado.leg.br/norma/572905/publicacao/43482324) |
| Lei 8.213/1991 | Salário-maternidade for every INSS category: who pays, minimum contributions, amount, unemployed women | Senado [550089](https://legis.senado.leg.br/norma/550089/publicacao/34619956) |
| Lei 11.770/2008 | Empresa Cidadã: +60 days, sharing with the father, half-day option | Senado [582192](https://legis.senado.leg.br/norma/582192/publicacao/34618993) |
| Lei 9.029/1995 | Pregnancy tests are a crime; remedies for discriminatory dismissal | Senado [550905](https://legis.senado.leg.br/norma/550905/publicacao/34619617) |
| Lei 8.112/1990 arts. 207–210 | Federal public servants | Senado [549988](https://legis.senado.leg.br/norma/549988/publicacao/34619938) |
| Lei 14.457/2022 | Priority for remote work and flexible hours for parents of children up to 6 | Senado [36360116](https://legis.senado.leg.br/norma/36360116/publicacao/36361273) |
| Leis 15.156/2025, 15.222/2025, 15.415/2026, 15.371/2026 | Recent changes: Zika (+60 days), hospital stays (leave counts from discharge), INSS must decide in 30 days, new paternity leave from 01/01/2027 | Each law's original published text on the Senado site |

**2. The check.** Every article was fetched and quoted word for word, including the amendment notes ("Redação dada pela Lei nº ..."), and each line of the old `laws.md` was compared with it. Where an article was amended recently, the amending law's own published text was read too, which is the cross-check: the compilation and the original amendment have to agree. No article text was filled in from memory.

What the check changed in the old `laws.md`:
- **Wrong reference fixed.** It cited "CF art. 7º, parágrafo único" for domestic workers' rights. Article 7º has no parágrafo único any more; the provision is **§1º**.
- **Two unsupported claims removed.** "It applies even if the employer didn't know about the pregnancy", and "if dismissed she can ask for reinstatement or compensation", had no article in any official text we read (the first comes from court decisions). The bot may only say what it can cite, so they went. For dismissal, it now cites Lei 9.029 art. 4º, which does say it, for discriminatory dismissal.
- **Confirmed word for word:** LC 150 arts. 1º, 2º, 9º, 17, 18, 21 and 25; ADCT art. 10, II, b; CLT art. 391-A; Lei 8.213 art. 73, I.

What was added: a section per kind of work (CLT, domestic, without a work card, day worker up to 2 days a week, self-employed or MEI, unemployed, rural, federal servant), and the rights that apply to all of them: hospital stays, premature birth, Zika, adoption, death of the mother, consultations, hazardous work, miscarriage, breastfeeding, nurseries, Empresa Cidadã, discrimination, flexible work, and the father's leave. The bot now asks what kind of work she does before giving deadlines, and the dossiê shows the rights for her kind of work.

**3. Not settled, so not claimed.** These go to a person, not to the bot:
- **STF, ADI 7.495 (23/09/2026).** The Senado's index of Lei 11.770 records a decision that all mothers, biological or adoptive, CLT or public servant, get the same 120 + 60 days. We could not read the decision on the STF site (its pages load the decisions by script). `laws.md` does not rely on it until someone confirms it.
- **Two articles numbered 73-A.** Lei 15.415/2026 (INSS 30-day deadline, in force) and Lei 15.371/2026 (salário-paternidade, from 01/01/2027) both add an "art. 73-A" to Lei 8.213. `laws.md` cites the first by its law, not by number.
- **Federal servants who adopt.** Lei 8.112 art. 210 still says 90 or 30 days, which may have been overtaken by the courts. The bot says it isn't sure and sends her to HR, the union and the Defensoria.
- **State and municipal servants** have their own statutes, not covered.

**4. Keeping it current.** Laws change: four laws changing these articles were published between July 2025 and May 2026. [`check_laws.py`](check_laws.py) runs every Monday on GitHub Actions ([`check-laws.yml`](.github/workflows/check-laws.yml)) and checks three things against a recorded baseline:
1. The **Senado's index of each law**, which lists every act that amended it. A new entry is the clearest signal.
2. A **fingerprint of every article** `laws.md` relies on, from the compiled text, so a change the index misses still shows up.
3. The **DOU search**, for publications in the last week that name these laws. It's where a change appears first, but in.gov.br drops automated connections often, so a DOU failure is reported and never treated as a change.

If something changed, it opens a GitHub issue with the details. If the change is in the law itself (a new amending act, or an article's text changed), the bot also adds one sentence to answers about deadlines and amounts until someone reviews it: the law may have changed recently, confirm with the union or the Defensoria. A page that changed layout, or a DOU mention, goes to the issue only, so a website redesign never reaches a mother. The server reads `laws_status.json` from its own checkout, so the deployment has to `git pull` (daily is enough) for that warning to switch on and off. If the checker itself crashes, the GitHub run fails and emails the owner instead of filing a law issue. It refuses to record a baseline while any source is unreadable, so an outage can't silently stop it watching a law. It never edits `laws.md` itself: a wrong legal claim reaching a mother is worse than a stale one. After a person updates `laws.md`, they run the workflow with **accept**, which records the new baseline.

Not yet done: the checker has only run against saved test pages, not live, because the build machine couldn't reach these sites directly. Its first run on GitHub records the baseline.

## Stack
Python + FastAPI · Claude (`claude-sonnet-5-5`, reads screenshots directly) · ElevenLabs (speech-to-text + voice replies) · ffmpeg · fpdf2 · WhatsApp-style web chat (a Twilio WhatsApp path is in progress on the `twilio` branch).

## What's next
Real WhatsApp number · state and municipal public servants (each has its own statute) · proactive reminders before key dates · partnerships with domestic workers' unions (FENATRAD) and the Defensoria.

## Files
| File | Job |
|---|---|
| `app.py` | Receives WhatsApp messages (Twilio), routes them, sends replies |
| `brain.py` | Claude prompt + rules; `job_protection_end()` computes the date in code |
| `voice.py` | ElevenLabs speech-to-text and text-to-speech, ffmpeg → voice note |
| `dossie.py` | Builds the PDF |
| `store.py` | One JSON file per user, named by a salted hash (no phone stored) |
| `laws.md` | The law the app is allowed to use. Edit it, restart, done |
| `laws_sources.json` | The official URL and the articles watched for each law |
| `check_laws.py` | Weekly law-change check (Senado index, article fingerprints, DOU) |

## Run it (laptop)
1. `cp .env.example .env` and fill in `ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` and `HASH_SALT`.
2. Install: `uv venv .venv && uv pip install -p .venv -r requirements.txt` (also needs `ffmpeg`).
3. Start: `.venv/bin/uvicorn app:app --port 8000`, then open http://localhost:8000
4. Optional public link: `ngrok http --url=<your-static-domain> 8000`

## Test
`.venv/bin/python -m pytest -q test_offline.py` (no keys needed)
