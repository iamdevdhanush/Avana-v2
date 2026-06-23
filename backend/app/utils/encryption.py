import base64
import hashlib

from cryptography.fernet import Fernet

from app.config import settings


def _derive_fernet_key(secret: str) -> bytes:
    raw = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(raw)


def encrypt_api_key(api_key: str) -> str:
    key = _derive_fernet_key(settings.SECRET_KEY)
    f = Fernet(key)
    return f.encrypt(api_key.encode()).decode()


def decrypt_api_key(encrypted: str) -> str:
    key = _derive_fernet_key(settings.SECRET_KEY)
    f = Fernet(key)
    return f.decrypt(encrypted.encode()).decode()


def mask_api_key(api_key: str) -> str:
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return api_key[:8] + "*" * (len(api_key) - 8)
