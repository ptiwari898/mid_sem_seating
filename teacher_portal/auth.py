from __future__ import annotations

import secrets
import time

import bcrypt

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_SECONDS = 900


def generate_code() -> str:
    return secrets.token_urlsafe(8)


def hash_code(plain_code: str) -> str:
    return bcrypt.hashpw(plain_code.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_code(plain_code: str, teachers_with_hashes: list[tuple[int, str]]) -> int | None:
    encoded = plain_code.encode("utf-8")
    for teacher_id, code_hash in teachers_with_hashes:
        if bcrypt.checkpw(encoded, code_hash.encode("utf-8")):
            return teacher_id
    return None


def lockout_seconds_left(
    failed_attempts: int,
    last_failure: float,
    now: float | None = None,
    max_attempts: int = MAX_LOGIN_ATTEMPTS,
    lockout_seconds: int = LOCKOUT_SECONDS,
) -> int:
    """Seconds a login stays blocked after too many failures; 0 means a try is allowed."""
    if failed_attempts < max_attempts:
        return 0
    elapsed = (time.time() if now is None else now) - last_failure
    return max(0, int(lockout_seconds - elapsed))
