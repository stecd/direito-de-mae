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
leave start/end dates · letter to patroa · evidence thumbnails inside the PDF · backup web chat page · clarifying-question flow for a missing due date.

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
