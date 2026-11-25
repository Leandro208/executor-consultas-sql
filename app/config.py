"""Configuracao da aplicacao e chaves de seguranca."""

from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"

load_dotenv(BASE_DIR / ".env")


def _load_or_create_secret_key() -> str:
    """Carrega EXECUTOR_SECRET_KEY do ambiente ou cria uma chave persistida."""
    key = os.environ.get("EXECUTOR_SECRET_KEY", "").strip()
    if key:
        return key

    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    key_file = INSTANCE_DIR / "secret.key"
    if key_file.exists():
        return key_file.read_text(encoding="utf-8").strip()

    key = Fernet.generate_key().decode()
    key_file.write_text(key, encoding="utf-8")
    try:
        key_file.chmod(0o600)
    except OSError:
        pass
    return key


class Config:
    SECRET_KEY = _load_or_create_secret_key()
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "EXECUTOR_DATABASE_URL",
        f"sqlite:///{INSTANCE_DIR / 'executor.db'}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    EXECUTOR_HOST = os.environ.get("EXECUTOR_HOST", "127.0.0.1")
    EXECUTOR_PORT = int(os.environ.get("EXECUTOR_PORT", "5000"))

    # Valores iniciais de configuracao (podem ser alterados pela tela /configuracoes)
    DEFAULT_ROW_LIMIT = 100
    DEFAULT_TIMEOUT_SECONDS = 30
    DEFAULT_EXPORT_LIMIT = 50_000
    MAX_ROW_LIMIT = 100_000
