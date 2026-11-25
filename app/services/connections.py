"""Criacao e cache de engines do PostgreSQL de destino."""

from __future__ import annotations

import threading
import time
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from ..crypto import decrypt_password
from ..models import Conexao

_lock = threading.Lock()
_engines: dict[tuple, Engine] = {}


def _cache_key(conexao: Conexao, timeout_seg: int) -> tuple:
    return (
        conexao.id,
        conexao.host,
        conexao.porta,
        conexao.database,
        conexao.usuario,
        conexao.senha_cifrada,
        conexao.sslmode,
        timeout_seg,
    )


def build_url(conexao: Conexao) -> str:
    senha = quote_plus(decrypt_password(conexao.senha_cifrada))
    usuario = quote_plus(conexao.usuario or "")
    return (
        f"postgresql+psycopg2://{usuario}:{senha}"
        f"@{conexao.host}:{conexao.porta}/{conexao.database}"
        f"?sslmode={conexao.sslmode}"
    )


def get_engine(conexao: Conexao, timeout_seg: int | None = None) -> Engine:
    timeout = int(timeout_seg or conexao.timeout_seg or 30)
    key = _cache_key(conexao, timeout)
    with _lock:
        engine = _engines.get(key)
        if engine is None:
            options = (
                f"-c statement_timeout={timeout * 1000} "
                "-c default_transaction_read_only=on "
                "-c application_name=executor_sql"
            )
            engine = create_engine(
                build_url(conexao),
                connect_args={"options": options, "connect_timeout": 10},
                pool_pre_ping=True,
                pool_size=2,
                max_overflow=2,
                pool_recycle=1800,
            )
            _engines[key] = engine
        return engine


def dispose_connection(conexao: Conexao) -> None:
    """Descarta engines em cache de uma conexao (apos edicao/remocao)."""
    with _lock:
        chaves = [k for k in _engines if k[0] == conexao.id]
        for k in chaves:
            engine = _engines.pop(k)
            engine.dispose()


def test_connection(conexao: Conexao) -> tuple[bool, int, str]:
    """Testa a conexao. Retorna (ok, latencia_ms, mensagem)."""
    inicio = time.perf_counter()
    try:
        engine = get_engine(conexao, timeout_seg=10)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        latencia = int((time.perf_counter() - inicio) * 1000)
        return True, latencia, "Conexao bem-sucedida."
    except Exception as exc:  # noqa: BLE001 - mensagem repassada ao usuario
        latencia = int((time.perf_counter() - inicio) * 1000)
        return False, latencia, str(exc)
