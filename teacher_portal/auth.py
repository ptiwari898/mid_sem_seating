from __future__ import annotations

import secrets

import bcrypt


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
