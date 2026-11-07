## Short and Honest: privacy facts, plain-word commands, rights by work type

### Why
A web-chat rehearsal before the first WhatsApp test showed four problems in what the bot says:
1. Asked "se minha patroa me levar para a justiça, eles podem ler estas mensagens?", it answered "Não sei com certeza". Claude's instructions described the law but nothing about the privacy system Phase 2 built.
2. It told her "O PDF só é gerado se você escrever RESUMO", which is false: natural-language requests work.
3. Replies ran 7–9 sentences (500–700 characters), against a rule of 4. That's hard to read for the users this serves, and each voice reply costs as many ElevenLabs credits as it has characters.
4. After working out she is a diarista (2 days a week, so not an employee), it still cited CLT art. 392 (paid time off for prenatal visits), which is an employee right.

### What changed
- `brain.py` SYSTEM prompt:
  - New rule 10 and a **FATOS SOBRE VOCÊ** block: what's kept, the per-user key destroyed on deletion, 90/365-day auto-delete, Twilio cleanup, and the phone as the main risk (disappearing messages, neutral contact name). Privacy questions are answered from these facts; legal questions about courts go to the Defensoria.
  - Rule 5: at most 3 short sentences and 350 characters, one question at the end, no repeated contact list.
  - Rule 7: she never has to type an exact word; "RESUMO gera o PDF" is gone.
  - New rule 1: once her work type is known, cite only rights for that type. Employee rights (CLT, LC 150) are never cited for autônoma, diarista, MEI or desempregada.
  - Rules renumbered 0–10 (the old rule 9 sat between 6 and 7).
- `brain.think()` takes `work_type`; `app.py` passes the stored one, so every turn knows it, not only the turn that learned it.
- `test_prompt.py`: 8 tests. The prompt's day counts must equal `store.py`'s, the facts and rules are present, the 350 is interpolated, rules are numbered in order, and the handler passes the stored work type. Test stubs in `test_safety.py` accept the new argument.

### What did NOT change
Law text (`laws.md`), dates, onboarding, commands and their code paths, storage.

### Verification
- `python -m pytest -q`: 64 passed.
- Real Claude through the web chat (dry run, no WhatsApp), with the questions from the screenshots:
  - Claude's reply lengths were 338, 273 and 280 characters (previously 500–700).
  - The falta question got an answer for an autônoma, with no CLT citation.
  - The courts question got "Não sou advogada… Defensoria", what we keep, that deletion makes it unreadable, and "o maior risco é o seu celular".
  - "como eu pego o pdf?" returned the resumo directly.

### Known gap (not in this PR)
With `VOICE_REPLIES=1`, ElevenLabs keeps a history of every voice reply's text in our account. Personal replies would sit there. The privacy facts only claim what *we* keep, so they stay true, but the gap should be closed: delete each history item after generating it (needs the key's history-write permission) or use a zero-retention setting.
