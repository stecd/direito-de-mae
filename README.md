# Direito de Mãe

WhatsApp helper for pregnant domestic workers in Brazil: rights from curated law (`laws.md`), a dated evidence diary, and a **DOSSIÊ** PDF. **APAGAR** deletes everything.

## Files
| File | Job |
|---|---|
| `app.py` | Receives WhatsApp messages (Twilio), routes them, sends replies |
| `brain.py` | Claude prompt + rules; `job_protection_end()` computes the date in code |
| `voice.py` | ElevenLabs speech-to-text and text-to-speech, ffmpeg → voice note |
| `dossie.py` | Builds the PDF |
| `store.py` | One JSON file per user, named by a salted hash (no phone stored) |
| `laws.md` | The law the app is allowed to use. Edit it, restart, done |

## Run it (laptop)
1. `cp .env.example .env` and fill in the keys.
2. Terminal 1: `.venv/bin/uvicorn app:app --port 8000`
3. Terminal 2: `ngrok http --url=<your-static-domain> 8000`
4. Twilio console → Messaging → Try it out → WhatsApp sandbox settings → "When a message comes in": `https://<your-static-domain>/whatsapp`, method POST.
5. From your phone, send the sandbox `join <code>` message, then say "oi".

## Test
`.venv/bin/python -m pytest -q test_offline.py` (no keys needed)
