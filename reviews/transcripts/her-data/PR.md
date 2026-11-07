## Her Data, Her Choice — Phase 2 safety, onboarding and plain-word commands

### Why
The person this serves is a pregnant domestic worker whose employer may pick up her phone. Phase 1 kept her evidence in plain JSON, served files from guessable URLs, left every message on Twilio, logged transcripts, and greeted her with a consent footer. "APAGAR apaga tudo" was not true. And it assumed she would type exact command words.

### What changed
**Storage (`store.py`)**
- Every user file and media file is encrypted (Fernet) with a random key that belongs to that user only; the key is wrapped by `MASTER_KEY`.
- `delete()` removes the key first (crypto-shredding): a backup copy of her file is unreadable afterwards.
- `sweep()` deletes users silent for 90 days (365 after `SALVAR`) and resumo PDFs older than an hour. Runs every 10 min in the app's lifespan task.
- Pre-encryption plaintext files still load and are re-saved encrypted.
- Without `MASTER_KEY` it creates a dev key in `data/` and warns. This is on the go-live checklist.

**Exposure (`app.py`)**
- `/media` links are HMAC-signed and expire after 15 minutes; the endpoint decrypts in memory.
- Twilio: inbound and outbound message SIDs are queued and deleted (with their media) 2 min later, retried up to 6 times.
- Logs carry no message text or transcripts; tracebacks keep file/line/exception type but drop the exception message; httpx request logging silenced.
- One message at a time per user (per-uid lock), so a slow message can't re-save data after APAGAR.

**Onboarding (`onboarding.py`)**
- New users are asked "1 escrita · 2 áudio · 3 os dois" (a voice-note answer counts as audio), then consent (SIM/NÃO), then a safety tip (disappearing messages, neutral contact name). No Claude call before SIM, and nothing but the mode and her first message is stored (encrypted); NÃO deletes everything. One exception: if her very first message is a voice note, ElevenLabs transcribes it before she has agreed, because we can't know what she said, or answer the mode question by voice, otherwise. The transcript is what's kept as her first message. Her first message is answered after she agrees.
- `say()` honours the chosen mode.

**Commands**
- `RESUMO` replaces `DOSSIÊ` in everything she sees ("dossiê", "relatório", "minhas provas" still work). New: `SALVAR`, `MEUS DADOS`, `MUDAR`.
- Claude returns an `intent` field, so "quero trocar minha escolha" or "me manda tudo que eu te contei" work without keywords. Exact words skip the AI call.
- Deleting is always a two-step confirm (keyword or natural language), cancelled by any other message or after 10 min.

**Voice**
- `VOICE_REPLIES=0` by default (text only) to save ElevenLabs credits; inbound voice notes are still transcribed.
- Fixed messages' voice notes are cached in `public/voice/` (committed; no personal data; ElevenLabs free-plan attribution in `public/README.md`). `import_voice_cache.py` refills it from ElevenLabs history at no cost.

### What did NOT change
Law answers, date maths, the PDF layout, the web chat UI (apart from link parsing and the "resumo.pdf" label), the Twilio webhook contract.

### Known gaps
- No 7-day warning before auto-delete: we don't store her number, so we can't write first. Needs her number stored encrypted plus a Meta template.
- The 10-minute janitor and the Twilio cleanup queue only run while the server runs; cleanup state is a small JSON of SIDs in `data/`.
- uvicorn's access log still shows the (expiring) signed links.
- WhatsApp-only behaviours (Twilio deletion, voice-note bubble, signature check) are untested until the WhatsApp checklist in PLAN.md.

### Verification
- `python -m pytest -q` → 42 passed (23 new in `test_safety.py`: encryption at rest, shredding vs backup, path traversal, legacy files, sweep, signed links incl. endpoint, Twilio cleanup retries, log scrubbing, onboarding end-to-end, consent refusal, APAGAR confirm/cancel, natural-language delete and mode change, SALVAR/MEUS DADOS, encrypted resumo, reply modes, voice cache).
- Manual run in the web chat with real Claude: onboarding → law answer with 20/06/2027 → mode change → MEUS DADOS → resumo PDF (signed link 200, unsigned 404) → "quero apagar tudo" → APAGAR. Server log contained none of the message text.
