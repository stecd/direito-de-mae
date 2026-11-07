## Forget the Voice: delete personal voice replies from ElevenLabs history

### Why
ElevenLabs keeps the text of every text-to-speech request in the account's speech history. With `VOICE_REPLIES=1`, every personal reply ("Anotei: a patroa disse que vai te mandar embora…") would sit in our ElevenLabs account indefinitely. That's outside our encryption, deletion and APAGAR. The previous PR left this as a known gap.

### What changed
- `voice.forget(text)`: searches up to 3 pages of 20 of the newest history items for our voice, and deletes those whose text matches exactly. Needs the API key's history read + write permission, which is now enabled.
- `app.spoken()`: for a personal reply (anything not in `FIXED`), calls `forget` in a `finally`. ElevenLabs logs the text as soon as it's requested, so deletion runs even if ffmpeg or the download fails afterwards. It runs in a background thread, so the reply isn't delayed by two extra API calls. Failures are logged without her words, and a reply not found in history is logged as an error.
- Fixed messages (welcome, consent, safety tip…) are not deleted. They hold no personal data, are cached in `public/voice/`, and `import_voice_cache.py` relies on finding them in history.

### Revised after the owner's pass: delete by id
- `voice.speak(..., on_history_id=...)` reads the `history-item-id` header ElevenLabs returns, before downloading the audio, and hands it back.
- `app.spoken()` deletes exactly that item (`voice.forget_id`). Matching by text is now only the fallback when the header is missing.
- So with many mothers at once, each deletion removes her own reply's item and nothing else, with no history search and no 60-item window. Identical replies to two mothers no longer cause a false "not found".
- Live: the header id matched the single history item for the reply; after `forget_id`, 0 left.

### What did NOT change
Speech-to-text (her incoming voice notes). Whether ElevenLabs retains STT audio or transcripts is not covered here (see Limits).

### Verification
- `pytest -q`: 75 passed. 4 new tests: exact-text deletion, personal vs fixed, failure logged without her words, not-found reported. Existing voice tests stub `forget`, so no test calls ElevenLabs.
- Live: generated a 25-character reply, found it in history, `forget` deleted 1, history then held 0.

### Limits
- If deletion fails (permission revoked, API down), the text stays in ElevenLabs history and only an error is logged.
- Only when ElevenLabs omits the id header does it fall back to searching the newest 60 items by text.
- If the ElevenLabs SDK retried a request on its own after `forget` ran, a duplicate could survive. The SDK only retries failed requests, which create no history item.
- Deletion runs in a background thread: a server restart in the second right after a reply would kill it, and that text would stay in ElevenLabs history without an error.
