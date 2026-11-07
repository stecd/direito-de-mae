# Direito de Mãe — Build Plan (60 min, one person)

## Architect review — what changed and why
- **85 → 60 min of build. The pitch video is not part of the 60.** Everything not in the demo story moved to Stretch.
- **Five small files + `laws.md`** (changed back from one file at the owner's request, for readability). Each file has one job.
- **JSON file per user instead of SQLite.** It holds `{history, entries, profile}`. APAGAR = delete one file + one media folder. No schema, no migrations.
- **No tool-use loop. One Claude call returns JSON** `{reply, entry, due_date}`. Python saves the entry and computes the dates. There is one round trip instead of 2–3, which leaves fewer parse failures and less latency. Dates are still computed in code, not by the model (that is the pitch point).
- **`dates.py` → one 6-line function `job_protection_end(due)` in `app.py`, with one assert.** Leave start/end dates moved to Stretch.
- **Cut: backup web page, letter to patroa, "forwarded?" detection.** Twilio does not reliably flag forwarded audio, so the reply just always asks "Quem mandou e quando?" for any audio that sounds like someone else's voice or message. Claude decides from the transcript.
- **Consent is no longer a state machine.** It is one line appended to the first reply when the user file is new.
- **Voice reply = text + voice note (TTS mp3 → ffmpeg → OGG Opus), both sent.** If TTS fails, she still gets the text.
- **Kept:** the user, the dossiê as the hero, citations only from laws.md, human handoff, APAGAR, hashed phone.

---

**One line:** A WhatsApp number a pregnant domestic worker in Brazil can text or voice-note. It tells her her rights (only from curated law, with the article cited), keeps a dated record of what happens to her, and turns it into a dossiê PDF for the sindicato or the Defensoria Pública.

**User:** a pregnant **domestic worker** (babá, empregada, cuidadora), with or without carteira assinada. She may not read well and lives in WhatsApp.

## Demo story (everything serves this)
1. **Voice note:** *"Sou babá, sem carteira, grávida de 6 meses, o nenê nasce em 20 de janeiro. A patroa disse que vai me mandar embora depois que ele nascer."* (The due date is in the script, so there is no clarifying round trip on stage.)
2. **Text + audio reply:** "Mesmo sem carteira você tem direitos. Ela não pode te dispensar até **20/06/2027** (LC 150 art. 25; ADCT art. 10, II, b). Guarde tudo: mande print, áudio ou me conte." Plus a consent line on first contact.
3. **Screenshot** of the patroa's message → "Anotei: 12/11 — patroa disse que vai te dispensar."
4. **Forwarded áudio** → transcribed → "Anotei. Quem mandou e quando?" → she answers → the entry is updated.
5. **DOSSIÊ** → the PDF arrives: timeline + rights + articles + "Não sou advogada. Sindicato das domésticas: [contato]. Defensoria: [contato]."
6. **APAGAR** → "Seus dados foram apagados."

## Stack
| Piece | Choice |
|---|---|
| Server | FastAPI + uvicorn, one file |
| Public URL | ngrok **free static domain** (same URL every restart; also serves outbound media) |
| WhatsApp | Twilio Sandbox, inbound webhook + outbound REST |
| Brain + vision | Claude `claude-sonnet-5-5`, one call per message, JSON out |
| Voice | ElevenLabs Scribe (`scribe_v1`, `language_code="por"`) + TTS (mp3) |
| PDF | `fpdf2` |
| Storage | `data/<sha256(phone)>.json` + `data/<hash>/` for media |

## Flow (`app.py`)
```
POST /whatsapp
  → return empty <Response/> immediately            # Twilio's 15s timeout
  → BackgroundTasks: handle(form)
handle:
  text = Body.strip().upper() without accents
  "APAGAR"  → delete json + folder → send text
  "DOSSIE"  → build PDF → send media URL /media/<hash>/dossie.pdf
  audio/*   → download (Twilio basic auth) → Scribe → text; voice_mode = True
  image/*   → download → base64 → Claude image block
  Claude(system = rules + laws.md, last 10 turns) → {reply, entry|null, due_date|null}
  if due_date: reply += code-computed date (job_protection_end)
  if entry: append {date_event, date_logged, source, summary, article}
  send reply text; if voice_mode: TTS mp3 → send /media/<hash>/<id>.mp3
GET /media/{path}  → FileResponse (public via ngrok)
```

## Files (small and separate, easy to read)
```
app.py      routes + handle(): picks the path (APAGAR / DOSSIE / audio / image / text)
brain.py    Claude call, system prompt, laws.md loading, job_protection_end()
voice.py    ElevenLabs Scribe (in) + TTS (out)
dossie.py   PDF builder
store.py    load/save/delete the per-user JSON file + media folder
laws.md     the curated law text
```

## Claude contract (system prompt essentials)
- Answer **only** from laws.md and always cite the article. If the question is not covered: "Não sei com certeza" + handoff.
- Never state a date yourself. Return `due_date` (ISO) when she mentions one. Code fills in the dates.
- When a right looks broken: "Não sou advogada" + sindicato first, then Defensoria.
- Max 3 short sentences, simple Portuguese, no markdown (WhatsApp shows the asterisks literally, and there is a 1600-character limit).
- Output **only** JSON. Parse with `json.loads` on the slice from the first `{` to the last `}`. On failure, send the raw text as the reply.

## Law corpus (`laws.md`, keep it under ~3 pages)
LC 150/2015 art. 25 + parágrafo único; ADCT art. 10, II, b; CLT 391-A (aviso prévio); Lei 8.213 art. 73, I (INSS pays salário-maternidade directly); LC 150 basics (carteira, FGTS, jornada); help contacts for the demo city.

## Gotchas → simplest fix
| Gotcha | Fix |
|---|---|
| Twilio webhook times out at 15s; Claude + Scribe + TTS takes longer | Return empty TwiML at once and reply via the REST API (`client.messages.create`) from a background task |
| `MediaUrl0` needs auth | `httpx.get(url, auth=(SID, TOKEN), follow_redirects=True)`. It redirects to S3, so redirects must be followed |
| Outbound media must be a public HTTPS URL | Serve `/media/...` from the same app, `PUBLIC_URL` = ngrok URL in `.env`. A new ngrok URL means updating both `.env` **and** the Twilio sandbox webhook. Keep ngrok running all day |
| ngrok free interstitial | Only shown to browsers, not to Twilio. Test the media URL with `curl`, not Chrome |
| Sandbox membership expires (~72h) and replies outside the 24h window fail | Re-send `join <code>` from the demo phone the morning of the demo. Every outbound message here answers an inbound one, so the 24h window is fine |
| Sandbox/trial throttling (~1 msg/sec, daily caps on trial) | Send text then audio in sequence. Don't spam test runs. Check the daily cap on the Twilio console |
| WhatsApp audio: mp3 arrives as an audio *file*, not a voice-note bubble | Convert TTS mp3 → OGG Opus: `ffmpeg -y -i in.mp3 -c:a libopus -b:a 32k -ac 1 -ar 48000 out.ogg`, serve as `audio/ogg`. Test on the phone at min 28; if it still shows as a file, keep it (it plays fine) |
| Inbound voice notes are `audio/ogg` (Opus) | Scribe accepts them as is, so no conversion is needed |
| Claude images: jpeg/png/gif/webp, ≤5MB, base64 | WhatsApp sends jpeg. Pass the `MediaContentType0` value as `media_type` |
| fpdf2 core fonts are latin-1 only: "—", curly quotes and emoji crash it | `s.encode("latin-1","replace").decode("latin-1")` on every string (ã/ç/ê survive) |
| Command matching: "Dossiê", "dossie", "DOSSIÊ." | Uppercase, strip accents and punctuation before comparing |
| Background task errors are silent | Wrap `handle` in try/except, log it, and send "Tive um problema, tente de novo." |

## Safety & privacy (pitch point)
- First reply on a new file adds: "Guardo o que você me mandar só para montar seu dossiê. Mande APAGAR para apagar tudo."
- Hashed phone, no name stored. The dossiê is "organiza suas provas", never "prova seu caso". Timestamps are not certified.
- Every broken right → "Não sou advogada" + sindicato, then Defensoria.
- Risk to name in the pitch: if the patroa takes her phone, the chat is visible.

---

## Timeline (60 min)
| Min | Do | Done when |
|---|---|---|
| 0–8 | `.env`, ngrok up, webhook set, FastAPI echo via REST from a background task | Your phone gets the echo |
| 8–20 | Claude JSON call + laws.md + `job_protection_end` (+1 assert) + JSON history | A text question gets a cited answer with the correct date |
| 20–28 | Audio in (auth download → Scribe) and TTS → ffmpeg OGG Opus voice note out via `/media` | Voice note → text + audio reply |
| 28–40 | Image → Claude, entries saved, DOSSIÊ → PDF, APAGAR, consent line | The PDF opens on your phone with 3 entries |
| 40–52 | Run the full demo story 2× end to end on the real phone. Fix what breaks | Two clean runs |
| 52–60 | Edge cases: off-topic question (→ handoff), APAGAR then DOSSIÊ (empty), bad JSON. Freeze the code | Nothing crashes. Commit |

**If behind at min 28:** drop TTS (text reply to voice). **At min 40:** drop images (log text/audio only). Never cut DOSSIÊ or APAGAR.

## Stretch (only after a frozen, working demo)
Done: leave start/end dates · evidence thumbnails inside the PDF · backup web chat page · clarifying question for a missing due date. Open: letter to patroa (held: sending a letter tips off the employer, so it needs a decision from the owner and the sindicato first).

## Not in v1 (say "next" in the pitch)
CLT/informal workers, proactive reminders, official Meta WhatsApp number, partnerships with sindicatos / FENATRAD / Defensoria.

## Pitch video (separate, ≈90s)
Problem (FAPESP Feb 2026: 8% of new mothers know all their rights, 54% had one broken; ~6M domestic workers, verify IBGE) → who she is → demo → why trust it (curated law, cited articles, code-computed dates, human handoff, APAGAR) → next.

## Setup checklist (before minute 0)
- [ ] Twilio sandbox joined from the demo phone; SID/token in `.env`
- [ ] Anthropic + ElevenLabs keys in `.env`; pick a pt-BR voice ID
- [ ] `brew install ngrok ffmpeg` + authtoken; `pip install fastapi uvicorn python-multipart twilio anthropic elevenlabs fpdf2 python-dotenv httpx`
- [ ] `laws.md` written; sindicato + Defensoria contacts for the demo city
- [ ] Demo assets ready on the phone: the screenshot of the patroa's message, an áudio to forward

---

# Phase 2 — Safety, onboarding, WhatsApp rollout

## 1. Security & safety (top of mind, not a feature)
**Threats, in order of likelihood:** (a) the patroa or a partner picks up her phone and reads the chat; (b) our server or a log leaks; (c) a third party (Twilio, Anthropic, ElevenLabs) keeps copies we forgot about; (d) the dossiê link is guessed or forwarded.

| Where data lives | What we do |
|---|---|
| **Her phone (WhatsApp chat)** | We can't delete it for her, so we teach her: on first contact and on `SEGURANÇA`, explain how to turn on **disappearing messages (24h / 7 days)** for this chat and how to save the contact under a neutral name. Replies never repeat the patroa's name or quote the evidence back. |
| **Twilio** | Twilio keeps message bodies and media by default. After each message is processed, call `messages(sid).delete()` and delete its media (inbound and outbound). Without this, `APAGAR` is a lie. |
| **Our server** | Encrypt each user file and media at rest (Fernet, a random key per user, stored wrapped by `MASTER_KEY`). `APAGAR` deletes the files **and** the per-user key (crypto-shredding: even backups become unreadable). Master key only in env, never in the repo. Keep the HMAC'd phone as the filename. |
| **Logs** | Log event types, timings and errors only, never message text, transcripts or phone numbers. Scrub `server.log`. |
| **AI vendors** | Send only what's needed (no phone, no name). Use Anthropic API (no training on API data by default) and ElevenLabs zero-retention mode where available; record each vendor's retention in the README. |
| **Dossiê / media links** | Replace public `/media/<uid>/<file>` with signed URLs (HMAC token, expire after ~15 min). Delete the PDF from disk after it's delivered. |

**Retention: auto-delete after X time.**
- Default: delete everything **90 days after her last message** (covers pregnancy → licença; she can extend).
- A sweep job (every 10 min) deletes expired users. **Built:** the deletion date is told at consent and in MEUS DADOS. **Not built yet:** the warning 7 days before. We don't store her number, so we can't write to her first; it needs her number stored encrypted (shredded with her data) plus a Meta-approved template. Planned message: "Seus dados serão apagados em 7 dias. Mande RESUMO para guardar uma cópia, ou SALVAR para manter." (Inside WhatsApp's 24h window only if she wrote recently; otherwise this needs an approved template — note for Meta API.)
- Commands: `APAGAR` (now, everything, with a confirm step: "Mande APAGAR de novo para confirmar"), `MEUS DADOS` (what we store + when it expires), `RESUMO` (her copy before deleting), `SALVAR` (resets the clock).

**Retrieval:** she owns the export. `RESUMO` is the retrieval path; optionally send it to a trusted second number (sister, sindicato) so evidence survives if her phone is taken or wiped.

**Legal (LGPD):** pregnancy is *dado sensível* (health). Needs explicit, specific consent, purpose limitation (only to build her dossiê), and a named controller. Consent is a clear yes in onboarding, not a footer line.

## Words she uses, not commands
- **"Dossiê" → "RESUMO"** in everything she sees ("seu resumo com tudo que aconteceu"). Still accept "dossiê", "relatório", "minhas provas" as synonyms. The PDF title can stay "Dossiê" since the sindicato/Defensoria read it.
- **Keywords are shortcuts, not the only way.** Each reply is classified by intent first: "quero trocar minha escolha", "prefiro áudio agora" → change mode; "me manda tudo que eu te contei" → resumo; "não apaga não" → salvar. Exact words (APAGAR, SALVAR, RESUMO, MUDAR) skip the AI call. Claude's JSON gets an `intent` field.
- **Deleting is the exception:** a natural-language delete request ("quero apagar tudo") always gets a confirm step, so a misread never wipes her evidence.

## 2. Onboarding interview
Replaces the one-line consent footer. Short, one question per message, works by text **or** voice (first message goes as both, since we don't know yet).

1. Hi + what this is (1 sentence) + "Não sou advogada."
2. **"Como prefere conversar? 1 Mensagem escrita · 2 Áudio · 3 Os dois"** — accept the number, the word, or infer from a voice-note reply. Never ask about literacy.
3. Consent: what we keep, why, for how long (90 days), how to delete. "Responda SIM para começar."
4. Safety tip: disappearing messages + neutral contact name.
5. Then the normal flow, honoring `profile.mode` (`text` → text only, `audio` → voice note + very short text, `both` → both). `MUDAR` re-asks anytime.

Implementation: `profile.onboarding_step` in the user JSON; `app.py` routes to `onboard()` until step == done. Nothing is stored except the mode until she says SIM.

## 3. Test plan — web first, WhatsApp only for WhatsApp things
**Everything in the web chat (`web.html`, `DRY_RUN=1`), zero Twilio messages:** onboarding (all 3 modes + voice reply + MUDAR), consent refusal, law answers + citations, dates, images, audio in/out, entries, RESUMO, APAGAR + confirm, MEUS DADOS, retention sweep (fake clock), encryption round-trip, signed-URL expiry, log scrubbing. Add these to `test_offline.py`.

**Then WhatsApp, only what the web can't prove** (budget ≈ 15–20 messages):
- [ ] Twilio signature validation on the real webhook
- [ ] Inbound voice note download (auth + redirect) → transcript
- [ ] Outbound OGG shows as a voice-note bubble
- [ ] Image download from Twilio
- [ ] RESUMO PDF arrives via signed URL and opens on the phone
- [ ] Twilio message + media deletion actually removes them (check console)
- [ ] Disappearing-messages instructions match the current WhatsApp UI

## 4. Future: Meta WhatsApp Cloud API instead of Twilio
Apply for the official Meta WhatsApp Business (Cloud) API: business verification + a dedicated number, usually a few days (can take longer). Why: no sandbox `join` code or 72h expiry, a real branded number, lower cost per conversation, direct media API, approved templates for the 7-day retention warning, one fewer vendor holding her messages. Keep `send()` / media download behind one small adapter so the switch is a single file.

## Phase 2 — build status (2026-11-06)
Built and tested on the web chat (`test_safety.py`, 21 tests; real Claude in the browser):
- Encrypted store with per-user keys and crypto-shredding; old plaintext files still load and are re-saved encrypted.
- Retention: 90 days after the last message, 1 year after SALVAR; sweep every 10 min; resumo PDFs removed after 1 hour.
- Signed media links (15 min). Twilio messages and media queued for deletion 2 min after sending, retried up to 6 times.
- Logs carry no message text or transcripts (the uvicorn access log does show the short-lived signed links).
- Onboarding: mode question (text/audio/both, voice answer = audio), consent (SIM/NÃO), safety tip, then her first message is answered.
- Commands by keyword or in her own words (Claude returns `intent`): RESUMO, SALVAR, APAGAR (always confirmed), MEUS DADOS, MUDAR.
Still to do on WhatsApp only: the checklist in section 3. Set `MASTER_KEY` in `.env` before going live.

## Go-live checklist (before the WhatsApp number goes public)
- [ ] **`MASTER_KEY` set in the server's environment** (generate it with the command in `.env.example`). Keep a copy in a password manager, not in the repo or next to `data/`. Without it, the server falls back to a development key file inside `data/`, which sits right next to the data it protects.
- [ ] `HASH_SALT` set to a long random value (not the default).
- [ ] Run **one** uvicorn worker on one instance. The per-user lock is in memory; several workers would let a slow message re-save data after APAGAR. Scaling out needs a file or database lock first.
- [ ] Voice replies: `VOICE_REPLIES=1` and ElevenLabs credits topped up (off by default; only for the demo for now).
- [ ] WhatsApp-only checklist in section 3 passed.
