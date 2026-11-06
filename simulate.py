"""Talk to the bot from the terminal WITHOUT spending WhatsApp messages.

Uses the real Claude + ElevenLabs, but prints replies instead of sending them.

  .venv/bin/python simulate.py                 # chat by typing
  type:  /img path/to/print.jpg  [caption]     # send a screenshot
         /audio path/to/voice.ogg              # send a voice note
         dossie | apagar                       # commands
"""
import mimetypes
import os
import shlex

os.environ["DRY_RUN"] = "1"
import app  # noqa: E402

PHONE = "whatsapp:+550000000000"  # fake test user, separate from your real phone

print("Direito de Mãe simulator. Ctrl+C to quit.")
while True:
    line = input("\nvocê> ").strip()
    form = {"From": PHONE, "Body": line, "NumMedia": "0"}
    if line.startswith(("/img ", "/audio ")):
        parts = shlex.split(line)
        path = parts[1]
        form.update(NumMedia="1", LocalMedia=path,
                    MediaContentType0="audio/ogg" if parts[0] == "/audio"
                    else (mimetypes.guess_type(path)[0] or "image/jpeg"),
                    Body=" ".join(parts[2:]))
    app.handle(form)
