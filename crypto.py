import os
import base64
import secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _get_key() -> bytes:
    key_b64 = os.getenv("ENCRYPTION_KEY")
    if not key_b64:
        raise RuntimeError("ENCRYPTION_KEY가 .env에 설정되지 않았습니다.")
    key = base64.urlsafe_b64decode(key_b64)
    if len(key) != 32:
        raise RuntimeError("ENCRYPTION_KEY는 32바이트(AES-256) 이어야 합니다.")
    return key


def encrypt_text(text: str) -> str:
    """AES-256-GCM 암호화 → base64url(nonce 12B + ciphertext)"""
    if not text:
        return ""
    aesgcm = AESGCM(_get_key())
    nonce = secrets.token_bytes(12)          # 96-bit nonce (GCM 권장)
    ciphertext = aesgcm.encrypt(nonce, text.encode("utf-8"), None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("utf-8")


def decrypt_text(encrypted: str) -> str:
    """AES-256-GCM 복호화"""
    if not encrypted:
        return ""
    aesgcm = AESGCM(_get_key())
    raw = base64.urlsafe_b64decode(encrypted.encode("utf-8"))
    nonce, ciphertext = raw[:12], raw[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")
