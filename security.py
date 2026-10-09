"""Хеш пароля: SHA-256 + соль, формат «соль$хеш»."""
import hashlib
import secrets


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(8).upper()
    return f"{salt}${hashlib.sha256((salt + password).encode()).hexdigest().upper()}"


def verify(password: str, stored: str) -> bool:
    return hash_password(password, stored.split("$")[0]) == stored