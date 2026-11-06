"""Per-user storage: one JSON file + one media folder per user.

The user's phone number is never stored. Files are named by an HMAC of the
phone with a secret salt, so the name can't be reversed by guessing numbers.
"""
import hashlib
import hmac
import json
import os
import shutil
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def user_id(phone: str) -> str:
    salt = os.environ.get("HASH_SALT", "troque-este-sal").encode()
    return hmac.new(salt, phone.encode(), hashlib.sha256).hexdigest()[:32]


def _file(uid: str) -> Path:
    return DATA_DIR / f"{uid}.json"


def media_dir(uid: str) -> Path:
    d = DATA_DIR / uid
    d.mkdir(exist_ok=True)
    return d


def exists(uid: str) -> bool:
    return _file(uid).exists()


def load(uid: str) -> dict:
    f = _file(uid)
    if not f.exists():
        return {"history": [], "entries": [], "profile": {}}
    return json.loads(f.read_text())


def save(uid: str, user: dict) -> None:
    user["history"] = user["history"][-20:]  # keep only recent turns
    _file(uid).write_text(json.dumps(user, ensure_ascii=False, indent=2))


def delete(uid: str) -> None:
    _file(uid).unlink(missing_ok=True)
    shutil.rmtree(DATA_DIR / uid, ignore_errors=True)
