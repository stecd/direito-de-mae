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
1. `cp .env.example .env` and fill in the keys. `PUBLIC_URL` must have no spaces and no trailing slash.
2. Terminal 1: `.venv/bin/uvicorn app:app --port 8000`
3. **Web demo:** open http://localhost:8000 (WhatsApp-style chat: voice notes, screenshots, drag and drop).

### Real WhatsApp (Twilio trial)
4. Terminal 2: `ngrok http --url=<your-static-domain> 8000`
5. Twilio Console → Try out WhatsApp → Receive a message → Inbound message settings → **Custom**:
   `https://<your-static-domain>/whatsapp`, method **POST**.
6. From the verified phone, WhatsApp "oi" to the trial number. No join code.

Each bot reply uses trial messages (text + voice note = 2, dossiê = 3). Test with the web chat or
`simulate.py` (no messages used) and save WhatsApp for the final runs.

## Test
`.venv/bin/python -m pytest -q test_offline.py` (no keys needed)
