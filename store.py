"""Per-user storage: one encrypted JSON file + one folder of encrypted media per user.

- The phone number is never stored. Files are named by an HMAC of the phone with a
  secret salt, so the name can't be reversed by guessing numbers.
- Every file is encrypted with a random key that belongs to that user only. The user
  key is itself encrypted ("wrapped") with MASTER_KEY from the environment.
- delete() destroys the user key first (crypto-shredding): even a copy of the data
  folder in an old backup can no longer be read.
- sweep() deletes users who have been quiet longer than their retention period.
"""
import hashlib
import hmac
import json
import logging
import os
import shutil
import time
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

log = logging.getLogger("direito.store")

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
KEYS_DIR = DATA_DIR / "_keys"
KEYS_DIR.mkdir(exist_ok=True)

class Unreadable(Exception):
    """Her file exists but can't be decrypted (e.g. MASTER_KEY changed). APAGAR still works."""


DEFAULT_KEEP_DAYS = 90   # covers pregnancy to the end of the leave; resets on every message
SAVED_KEEP_DAYS = 365    # after she sends SALVAR
DAY = 86400


def _master_key() -> bytes:
    key = os.environ.get("MASTER_KEY")
    if not key:
        # Local development only: a key file next to the data. In production set MASTER_KEY.
        f = DATA_DIR / "_dev_master.key"
        if not f.exists():
            f.write_bytes(Fernet.generate_key())
            log.warning("MASTER_KEY not set: created a development key at %s", f)
        return f.read_bytes().strip()
    return key.encode()


def _master() -> Fernet:
    return Fernet(_master_key())


def secret() -> bytes:
    """Server secret used for signing media links (derived, never the key itself)."""
    return hashlib.sha256(b"links:" + _master_key()).digest()


def user_id(phone: str) -> str:
    salt = os.environ.get("HASH_SALT", "troque-este-sal").encode()
    return hmac.new(salt, phone.encode(), hashlib.sha256).hexdigest()[:32]


def _file(uid: str) -> Path:
    return DATA_DIR / f"{uid}.json"


def _keyfile(uid: str) -> Path:
    return KEYS_DIR / f"{uid}.key"


def _fernet(uid: str, create: bool = True) -> Fernet | None:
    kf = _keyfile(uid)
    if not kf.exists():
        if not create:
            return None
        kf.write_bytes(_master().encrypt(Fernet.generate_key()))
    try:
        return Fernet(_master().decrypt(kf.read_bytes()))
    except InvalidToken:
        raise Unreadable(uid) from None


def media_dir(uid: str) -> Path:
    d = DATA_DIR / uid
    d.mkdir(exist_ok=True)
    return d


def exists(uid: str) -> bool:
    return _file(uid).exists()


def new_user() -> dict:
    return {"history": [], "entries": [], "profile": {}}


def load(uid: str) -> dict:
    f = _file(uid)
    if not f.exists():
        return new_user()
    raw = f.read_bytes()
    if raw.lstrip().startswith(b"{"):  # file from before encryption: read it, re-saved encrypted
        return json.loads(raw)
    fer = _fernet(uid, create=False)
    if fer is None:  # key was shredded
        return new_user()
    try:
        return json.loads(fer.decrypt(raw))
    except InvalidToken:
        raise Unreadable(uid) from None


def save(uid: str, user: dict) -> None:
    user["history"] = user["history"][-20:]  # keep only recent turns
    user["last_seen"] = time.time()
    data = json.dumps(user, ensure_ascii=False).encode()
    _file(uid).write_bytes(_fernet(uid).encrypt(data))


def write_media(uid: str, name: str, data: bytes) -> str:
    (media_dir(uid) / name).write_bytes(_fernet(uid).encrypt(data))
    return name


def read_media(uid: str, name: str) -> bytes | None:
    path = (DATA_DIR / uid / name).resolve()
    if DATA_DIR.resolve() not in path.parents or not path.is_file():
        return None
    raw = path.read_bytes()
    if not raw.startswith(b"gAAAAA"):  # media saved before encryption: encrypt it now
        write_media(uid, name, raw)
        return raw
    try:
        fer = _fernet(uid, create=False)
        return fer.decrypt(raw) if fer else None
    except (InvalidToken, Unreadable):
        return None


def delete(uid: str) -> None:
    _keyfile(uid).unlink(missing_ok=True)  # shred the key first
    _file(uid).unlink(missing_ok=True)
    shutil.rmtree(DATA_DIR / uid, ignore_errors=True)


def keep_days(user: dict) -> int:
    return int(user.get("profile", {}).get("keep_days") or DEFAULT_KEEP_DAYS)


def expires_at(user: dict, fallback: float | None = None) -> float:
    """Old files have no last_seen: count from the file's last change instead."""
    last = user.get("last_seen") or fallback or time.time()
    return float(last) + keep_days(user) * DAY


def sweep(now: float | None = None) -> list[str]:
    """Delete every user past their retention date, and delivered resumo PDFs and voice
    replies older than an hour. Returns the deleted user ids."""
    now = time.time() if now is None else now
    gone = []
    for f in DATA_DIR.glob("*.json"):
        uid = f.stem
        if uid.startswith("_"):
            continue
        mtime = f.stat().st_mtime
        try:
            user = load(uid)
        except Exception:  # unreadable: the promise still holds, by file age and default retention
            user = new_user()
        if now > expires_at(user, fallback=mtime):
            delete(uid)
            gone.append(uid)
    # Delivered files are only needed while Twilio fetches them (links last 15 min).
    for pattern in ("*/resumo_*.pdf", "*/resposta_*"):
        for f in DATA_DIR.glob(pattern):
            if now - f.stat().st_mtime > 3600:
                f.unlink(missing_ok=True)
    return gone
