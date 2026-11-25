"""Cifragem de senhas de conexao com Fernet."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app


def _fernet() -> Fernet:
    key = current_app.config["SECRET_KEY"]
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_password(plain: str | None) -> str:
    if not plain:
        return ""
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_password(token: str | None) -> str:
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError(
            "Nao foi possivel decifrar a senha da conexao. "
            "A chave secreta pode ter mudado."
        ) from exc
