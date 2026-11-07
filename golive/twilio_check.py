"""Read-only Twilio check. Sends nothing, costs nothing.

    python golive/twilio_check.py            # look
    python golive/twilio_check.py --purge    # delete every stored message (free; for the 4 from before cleanup existed)

Shows the account type, how many messages Twilio still STORES, and their status.
After a test run plus ~3 minutes, "stored" should drop to 0: that proves our cleanup deletes
her messages from Twilio. Deleted messages disappear from this list, so for how many trial
messages you have LEFT, use the console: Messaging → Try it out → WhatsApp → Free units tracker.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
from twilio.rest import Client  # noqa: E402

c = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
acct = c.api.v2010.accounts(os.environ["TWILIO_ACCOUNT_SID"]).fetch()
print(f"account: {acct.type} ({acct.status})")
msgs = c.messages.list(limit=100)
print(f"messages still stored on Twilio: {len(msgs)}")
for m in msgs[:20]:
    err = f" error {m.error_code}" if m.error_code else ""
    print(f"  {m.date_sent:%d/%m %H:%M}  {m.direction:<12} {m.status:<10} media={m.num_media}{err}")
if "--purge" in sys.argv:  # one-off: delete messages stored before automatic cleanup existed
    for m in msgs:
        c.messages(m.sid).delete()
    print(f"deleted {len(msgs)} stored message(s)")
if "--expect-empty" in sys.argv:
    sys.exit(0 if not msgs else 1)
