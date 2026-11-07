# Go live: order, scripts, budget

**Budgets (checked 06/11/2026)**
- **Twilio:** trial account, $0 balance. Free trial units: **100 WhatsApp messages in total, at most 50 per day, one every 3 s**. 4 used so far. Incoming and outgoing both counted here, to be safe.
- **ElevenLabs:** free plan, **~74 credits left**. 1 credit = 1 character of voice reply.
- **Claude:** pay-as-you-go, cents per message. Not a constraint.

The source of truth for messages left is **Twilio console → Messaging → Try it out → Send a WhatsApp message → Free units tracker**. Our cleanup deletes messages from Twilio, so the API can't count them afterwards. Look at the tracker before steps 3, 5 and 6.

| Step | What | WhatsApp msgs | ElevenLabs credits | When |
|---|---|---|---|---|
| 1 | MASTER_KEY + wipe test data | 0 | 0 | now |
| 2 | Full rehearsal in the web chat | 0 | 0 | now |
| 3 | Go live (server + ngrok + webhook) | 0 | 0 | test day |
| 4 | WhatsApp test, text only | **15** | 0 (+ 1 short voice note transcribed) | test day |
| 5 | Add credits, warm the voice cache | 0 | **~1,349** | after step 4 passes |
| 6 | WhatsApp test, voice | **13** | **~250** | same day as 5 |
| 7 | Demo rehearsal (once) | **21** | **~900** | demo day |
| 8 | Demo | **21** | **~900** | demo day |
| | **Total** | **70 + 4 used = 74 of 100** | **~3,400** | |

Daily cap check: steps 4 + 6 = 28 (+4 if the same UTC day as before = 32). Steps 7 + 8 = 42. Both stay under 50/day, **as long as 4–6 and 7–8 fall on different days**. If a step fails, re-run only the failing message, never the whole script. That leaves a buffer of 26 messages.

---

## 1 · MASTER_KEY + wipe test data (0 msgs, 0 credits)

Everything in `data/` today is test data, encrypted with a development key. It would become unreadable under the new key, so delete it first. `pede.ogg` and `teste.ogg` are audio test files; they stay.

```bash
rm -rf data/_keys data/_shared data/_dev_master.key data/*.json
```

```bash
.venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copy the output into **your password manager first**, then into `.env` as `MASTER_KEY=...`. If this key is lost, every stored record is unreadable. Never change it once real users exist.

```bash
.venv/bin/python -m pytest -q
```

Expect `56 passed`.

```bash
.venv/bin/python golive/preflight.py
```

Expect `READY`.

## 2 · Full rehearsal in the web chat (0 msgs, 0 credits)

```bash
DRY_RUN=1 VOICE_REPLIES=0 .venv/bin/uvicorn app:app --port 8000
```

Open http://127.0.0.1:8000 and send exactly the messages from step 4, including a real photo and a recorded voice note. Every reply should match the expected column. Fix anything here, where it costs nothing. Afterwards, wipe the rehearsal data: `rm -rf data/_keys data/_shared data/*.json`.

## 3 · Go live (0 msgs)

Two terminals. **One uvicorn worker, never `--workers`.** The APAGAR protection depends on it.

```bash
VOICE_REPLIES=0 .venv/bin/uvicorn app:app --port 8000
```

```bash
ngrok http --url=$(grep ^PUBLIC_URL .env | cut -d/ -f3) 8000
```

In the Twilio console, set the WhatsApp sender's **"When a message comes in"** to `<PUBLIC_URL>/whatsapp` (POST). It must match `PUBLIC_URL` exactly, or every message is rejected with 403.

```bash
.venv/bin/python golive/preflight.py --live
```

Expect `READY`: the forged webhook gets 403 and the unsigned media link gets 404. Optionally, delete the 4 old messages Twilio still stores (free):

```bash
.venv/bin/python golive/twilio_check.py --purge
```

## 4 · WhatsApp test, text only (15 msgs)

Use the phone that already worked with the bot. A trial number only reaches numbers already joined or verified. Wait for each reply before sending the next message. Each row lists what it proves; only send what's listed.

| # | You send | Expect back | Msgs | Proves |
|---|---|---|---|---|
| 1 | `Sou babá, sem carteira, grávida, o nenê nasce em 20 de janeiro` | Welcome + "1, 2 ou 3?" | 2 | webhook, signature, onboarding |
| 2 | 🎤 voice note, ~3 s: *"áudio"* | "Combinado, vou responder por áudio…" + consent (as **text**, voice is off) | 2 | voice-note download from Twilio + transcription |
| 3 | `sim` | Safety tip, then the answer to #1 with **20/06/2027** | 3 | consent, delayed first answer, dates |
| 4 | 📷 screenshot of a chat with the patroa | "Anotei: …" | 2 | image download from Twilio |
| 5 | `me manda tudo que eu te contei` | Resumo text + **PDF**. Open it on the phone. | 2 | natural-language intent, signed link reachable by Twilio |
| — | wait 3 minutes, then run `twilio_check.py` | `messages still stored on Twilio: 0` | 0 | **Twilio deletion works** |
| 6 | `APAGAR` | "Você quer mesmo apagar tudo?…" | 2 | confirm step |
| 7 | `APAGAR` | "Pronto. Seus dados foram apagados." | 2 | delete |

That's 15 messages. Then check the server: `ls data/` should show no `.json` file. Look at the terminal log too: it should show no message text.

If incoming messages show `error 12300` in `twilio_check.py` but replies arrived, it's only a warning. Change `media_type="application/xml"` to `"text/xml"` in `app.py`'s `/whatsapp` route.

## 5 · Add ElevenLabs credits, warm the cache (0 msgs, ~1,349 credits)

- Check on elevenlabs.io when the free plan's monthly credits reset. If that's before the demo, 10,000 is enough. Otherwise take the cheapest paid plan (Starter). It also gives the commercial license.
- If you upgrade, delete `public/voice/` and regenerate: free-plan clips keep free-plan terms.

```bash
.venv/bin/python import_voice_cache.py
```

```bash
.venv/bin/python golive/warm_voice.py
```

```bash
.venv/bin/python golive/warm_voice.py --yes
```

The first two are free. `import_voice_cache.py` copies clips that already exist in ElevenLabs' history, and `warm_voice.py` without `--yes` shows the exact cost (~1,349 today). The third generates the clips. Then commit `public/voice/`, so they're never paid for again.

## 6 · WhatsApp test, voice (13 msgs, ~250 credits)

Restart uvicorn with `VOICE_REPLIES=1`.

| # | You send | Expect back | Msgs | Credits |
|---|---|---|---|---|
| 1 | `oi` | Welcome as text **and** voice note (cached) | 3 | 0 |
| 2 | `2` | Consent as a **voice-note bubble** (not a file) | 2 | 0 |
| 2b | `sim` | Safety tip (voice, cached) | 2 | 0 |
| 3 | `qual o prazo da licença?` | Asks your due date or work type (voice) | 2 | ~250 |
| 4 | `APAGAR` | Confirm question (voice, cached after step 5) | 2 | 0 |
| 5 | `APAGAR` | "Pronto…" (voice, cached) | 2 | 0 |

Watch #1. The text and the voice note leave back to back, and the trial number allows one message every 3 s. If the voice note fails, `twilio_check.py` shows the error, and the fix is a short pause in `say()`.

## 7–8 · Demo rehearsal, then demo (21 msgs + ~900 credits each)

Mode **audio** (answer `2`), `VOICE_REPLIES=1`. Have the assets on the phone first: the patroa screenshot and a forwarded áudio.

1. 🎤 *"Sou babá, sem carteira, grávida de 6 meses, o nenê nasce em 20 de janeiro. A patroa disse que vai me mandar embora."* → welcome (text + voice)
2. `2` → consent (voice)
3. `sim` → safety tip + rights answer with 20/06/2027 (voice)
4. 📷 the screenshot → "Anotei…"
5. ↪️ the forwarded áudio → "Anotei. Quem mandou e quando?"
6. `Minha patroa, ontem` → entry updated
7. `RESUMO` → PDF + voice
8. `APAGAR`, then `APAGAR` → deleted

That's 9 sent and 12 received per run: 21. Run the rehearsal **once**. If it's clean, don't run it again before the demo.

## After the demo
- `VOICE_REPLIES=0` again.
- To go public: apply for the Meta WhatsApp Business API (PLAN.md §4). The trial number can only reach joined or verified phones.
