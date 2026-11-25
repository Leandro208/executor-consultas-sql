"""Analise do SQL informado pelo usuario.

- Mascara literais, identificadores citados e comentarios para que a deteccao de
  parametros nao encontre falsos positivos.
- Detecta placeholders no formato :nome (ignorando casts do PostgreSQL, ex.: ::text).
- Valida que o comando e de leitura e que ha apenas um statement.
"""

from __future__ import annotations

import re

PLACEHOLDER_RE = re.compile(r"(?<!:):([A-Za-z_][A-Za-z0-9_]*)")

ALLOWED_FIRST_TOKENS = {"SELECT", "WITH", "TABLE", "VALUES", "EXPLAIN"}


def _mask(sql: str) -> str:
    """Troca o conteudo de literais/comentarios por espacos."""
    out: list[str] = []
    i = 0
    n = len(sql)

    while i < n:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""

        # comentario de linha
        if ch == "-" and nxt == "-":
            while i < n and sql[i] != "\n":
                out.append("\n" if sql[i] == "\n" else " ")
                i += 1
            continue

        # comentario de bloco (com suporte a aninhamento)
        if ch == "/" and nxt == "*":
            depth = 1
            out.append("  ")
            i += 2
            while i < n and depth:
                if sql[i] == "/" and i + 1 < n and sql[i + 1] == "*":
                    depth += 1
                    out.append("  ")
                    i += 2
                elif sql[i] == "*" and i + 1 < n and sql[i + 1] == "/":
                    depth -= 1
                    out.append("  ")
                    i += 2
                else:
                    out.append("\n" if sql[i] == "\n" else " ")
                    i += 1
            continue

        # string com escape por duplicacao ('')
        if ch == "'":
            out.append(" ")
            i += 1
            while i < n:
                if sql[i] == "'" and i + 1 < n and sql[i + 1] == "'":
                    out.append("  ")
                    i += 2
                    continue
                if sql[i] == "'":
                    out.append(" ")
                    i += 1
                    break
                out.append("\n" if sql[i] == "\n" else " ")
                i += 1
            continue

        # identificador citado ("...")
        if ch == '"':
            out.append(" ")
            i += 1
            while i < n:
                if sql[i] == '"' and i + 1 < n and sql[i + 1] == '"':
                    out.append("  ")
                    i += 2
                    continue
                if sql[i] == '"':
                    out.append(" ")
                    i += 1
                    break
                out.append("\n" if sql[i] == "\n" else " ")
                i += 1
            continue

        # dollar-quoted ($tag$ ... $tag$)
        if ch == "$":
            match = re.match(r"\$[A-Za-z_0-9]*\$", sql[i:])
            if match:
                tag = match.group(0)
                end = sql.find(tag, i + len(tag))
                if end == -1:
                    block = sql[i:]
                    i = n
                else:
                    block = sql[i : end + len(tag)]
                    i = end + len(tag)
                out.append("".join("\n" if c == "\n" else " " for c in block))
                continue

        out.append(ch)
        i += 1

    return "".join(out)


def detect_params(sql: str) -> list[str]:
    """Retorna os nomes de parametros na ordem de aparicao, sem duplicatas."""
    masked = _mask(sql or "")
    seen: list[str] = []
    for match in PLACEHOLDER_RE.finditer(masked):
        nome = match.group(1)
        if nome not in seen:
            seen.append(nome)
    return seen


def convert_placeholders(sql: str) -> str:
    """Converte :nome para %(nome)s fora de literais e comentarios."""
    masked = _mask(sql or "")
    partes: list[str] = []
    ultimo = 0
    for match in PLACEHOLDER_RE.finditer(masked):
        inicio, fim = match.span()
        partes.append(sql[ultimo:inicio])
        partes.append(f"%({match.group(1)})s")
        ultimo = fim
    partes.append(sql[ultimo:])
    return "".join(partes)


def validate_read_only(sql: str) -> tuple[bool, str | None]:
    """Verifica se o SQL e um unico comando de leitura."""
    raw = (sql or "").strip()
    if not raw:
        return False, "A consulta SQL esta vazia."

    masked = _mask(raw).strip()
    if not masked:
        return False, "A consulta SQL esta vazia."

    # permite um unico ponto-e-virgula final
    sem_ponto = masked.rstrip(";").strip()
    if ";" in sem_ponto:
        return False, "Envie apenas um comando SQL por consulta."

    first = re.match(r"[A-Za-z]+", sem_ponto)
    if not first:
        return False, "Nao foi possivel identificar o comando SQL."

    token = first.group(0).upper()
    if token not in ALLOWED_FIRST_TOKENS:
        return (
            False,
            f"Somente consultas de leitura sao permitidas "
            f"({', '.join(sorted(ALLOWED_FIRST_TOKENS))}). Recebido: {token}.",
        )

    return True, None
