import os
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet

DATA_DIR = Path(__file__).parent / "data"

STATE_FILES = [
    "users.json",
    "notified.json",
    "schedule_cache.json",
    "update_offset.json",
]


def get_fernet() -> Optional["object"]:
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        return None
    return Fernet(key.encode())


def decrypt_state() -> None:
    fernet = get_fernet()
    if fernet is None:
        return
    for name in STATE_FILES:
        enc_path = DATA_DIR / f"{name}.enc"
        if not enc_path.exists():
            continue
        plain = fernet.decrypt(enc_path.read_bytes())
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        (DATA_DIR / name).write_bytes(plain)


def encrypt_state() -> None:
    fernet = get_fernet()
    if fernet is None:
        return
    for name in STATE_FILES:
        plain_path = DATA_DIR / name
        if not plain_path.exists():
            continue
        encrypted = fernet.encrypt(plain_path.read_bytes())
        (DATA_DIR / f"{name}.enc").write_bytes(encrypted)
