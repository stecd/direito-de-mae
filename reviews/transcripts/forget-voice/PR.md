## Forget the Voice: delete personal voice replies from ElevenLabs history

### Why
ElevenLabs keeps the text of every text-to-speech request in the account's speech history. With `VOICE_REPLIES=1`, every personal reply ("Anotei: a patroa disse que vai te mandar embora…") would sit in our ElevenLabs account indefinitely. That's outside our encryption, deletion and APAGAR. The previous PR left this as a known gap.

### What changed
- `voice.forget(text)`: lists the 20 most recent history items for our voice and deletes those whose text matches exactly. Needs the API key's history read + write permission, which is now enabled.
- `app.spoken()`: after generating a personal reply (anything not in `FIXED`), calls `forget`. Failures are logged without her words (scrubbed traceback), and the reply still goes out. A reply not found in history is logged as an error.
- Fixed messages (welcome, consent, safety tip…) are not deleted. They hold no personal data, are cached in `public/voice/`, and `import_voice_cache.py` relies on finding them in history.

### What did NOT change
Speech-to-text (her incoming voice notes). Whether ElevenLabs retains STT audio or transcripts is not covered here (see Limits).

### Verification
- `pytest -q`: 75 passed. 4 new tests: exact-text deletion, personal vs fixed, failure logged without her words, not-found reported. Existing voice tests stub `forget`, so no test calls ElevenLabs.
- Live: generated a 25-character reply, found it in history, `forget` deleted 1, history then held 0.

### Limits
- If deletion fails (permission revoked, API down), the text stays in ElevenLabs history and only an error is logged.
- Only the last 20 history items are searched. Replies are deleted immediately after generation, so the match is near the top, but heavy concurrent traffic could push it out.
