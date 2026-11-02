"""Authentification : hash de mots de passe (PBKDF2), jeton CSRF, limitation des tentatives."""
import hashlib
import hmac
import os
import re
import secrets
import time
from collections import defaultdict, deque

ITERATIONS = 240_000
MIN_LEN = 10

# tentatives de connexion échouées par IP (mémoire du processus)
MAX_ATTEMPTS = 5
WINDOW_S = 300
_attempts: dict[str, deque] = defaultdict(deque)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt, digest = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iters))
        return hmac.compare_digest(dk.hex(), digest)
    except (ValueError, TypeError):
        return False


def password_errors(password: str, confirmation: str | None = None) -> list[str]:
    errors = []
    if len(password or "") < MIN_LEN:
        errors.append(f"Le mot de passe doit contenir au moins {MIN_LEN} caractères.")
    elif not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password)):
        errors.append("Le mot de passe doit contenir au moins une lettre et un chiffre.")
    if confirmation is not None and password != confirmation:
        errors.append("Les deux mots de passe ne correspondent pas.")
    return errors


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def csrf_ok(session_token: str | None, form_token: str | None) -> bool:
    return bool(session_token) and bool(form_token) and hmac.compare_digest(session_token, form_token)


def too_many_attempts(key: str, now: float | None = None) -> bool:
    now = now or time.time()
    q = _attempts[key]
    while q and now - q[0] > WINDOW_S:
        q.popleft()
    return len(q) >= MAX_ATTEMPTS


def record_failure(key: str, now: float | None = None) -> None:
    _attempts[key].append(now or time.time())


def reset_attempts(key: str | None = None) -> None:
    if key is None:
        _attempts.clear()
    else:
        _attempts.pop(key, None)


def auth_disabled() -> bool:
    """FROIDPRO_AUTH=off désactive la connexion (usage local uniquement)."""
    return os.getenv("FROIDPRO_AUTH", "on").lower() in ("off", "0", "false")
