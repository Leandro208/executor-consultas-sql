"""Execucao segura das consultas cadastradas."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, datetime, time as dt_time
from decimal import Decimal, InvalidOperation

from ..models import Consulta, Parametro
from .connections import get_engine
from .sqlparser import convert_placeholders, detect_params, validate_read_only


class ConsultaInvalida(ValueError):
    """SQL recusado pela validacao."""


class ParametrosInvalidos(ValueError):
    """Parametros informados nao conferem com a definicao da consulta."""


@dataclass
class ExecResult:
    columns: list[str] = field(default_factory=list)
    rows: list[list] = field(default_factory=list)
    truncated: bool = False
    duration_ms: int = 0

    @property
    def total_linhas(self) -> int:
        return len(self.rows)

    def to_records(self) -> list[dict]:
        """Converte para lista de dicionarios com chaves unicas."""
        chaves: list[str] = []
        vistos: dict[str, int] = {}
        for col in self.columns:
            nome = col or "coluna"
            if nome in vistos:
                vistos[nome] += 1
                nome = f"{nome}_{vistos[nome]}"
            else:
                vistos[nome] = 1
            chaves.append(nome)
        return [dict(zip(chaves, linha)) for linha in self.rows]


def _converter_valor(param: Parametro, bruto: str) -> object:
    texto = (bruto or "").strip()
    tipo = (param.tipo or "texto").lower()

    if texto == "":
        if param.obrigatorio:
            raise ParametrosInvalidos(
                f"O parametro '{param.rotulo or param.nome}' e obrigatorio."
            )
        return None

    if tipo == "numero":
        try:
            if "." in texto or "," in texto:
                return Decimal(texto.replace(",", "."))
            return int(texto)
        except (InvalidOperation, ValueError) as exc:
            raise ParametrosInvalidos(
                f"O parametro '{param.rotulo or param.nome}' deve ser numerico."
            ) from exc

    if tipo == "data":
        try:
            if "T" in texto or " " in texto:
                return datetime.fromisoformat(texto.replace(" ", "T"))
            return date.fromisoformat(texto)
        except ValueError as exc:
            raise ParametrosInvalidos(
                f"O parametro '{param.rotulo or param.nome}' deve ser uma data "
                "(AAAA-MM-DD)."
            ) from exc

    if tipo == "booleano":
        if texto.lower() in {"true", "1", "sim", "s", "t", "verdadeiro"}:
            return True
        if texto.lower() in {"false", "0", "nao", "n", "f", "falso"}:
            return False
        raise ParametrosInvalidos(
            f"O parametro '{param.rotulo or param.nome}' deve ser verdadeiro/falso."
        )

    return texto


def preparar_valores(consulta: Consulta, valores: dict[str, str]) -> dict[str, object]:
    """Converte os valores do formulario para os tipos definidos."""
    definidos = {p.nome: p for p in consulta.parametros_ordenados}
    ligados: dict[str, object] = {}

    for nome, param in definidos.items():
        ligados[nome] = _converter_valor(param, valores.get(nome, param.valor_padrao))

    return ligados


def parametros_faltantes(consulta: Consulta) -> list[str]:
    """Nomes de placeholders no SQL que ainda nao possuem definicao."""
    definidos = {p.nome for p in consulta.parametros}
    return [n for n in detect_params(consulta.sql) if n not in definidos]


def validar_antes_de_salvar(sql: str) -> tuple[bool, str | None]:
    return validate_read_only(sql)


def _normalizar_celula(valor: object) -> object:
    if valor is None:
        return None
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, (datetime, date, dt_time)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, (bytes, bytearray, memoryview)):
        dados = bytes(valor)
        return f"<{len(dados)} bytes>"
    if isinstance(valor, (int, float, str)):
        return valor
    if isinstance(valor, (list, dict)):
        return str(valor)
    return str(valor)


def executar(
    consulta: Consulta,
    valores: dict[str, str],
    limite: int,
    timeout_seg: int,
    limite_maximo: int,
) -> ExecResult:
    ok, erro = validate_read_only(consulta.sql)
    if not ok:
        raise ConsultaInvalida(erro or "SQL invalido.")

    limite = max(1, min(int(limite), int(limite_maximo)))
    ligados = preparar_valores(consulta, valores)

    engine = get_engine(consulta.conexao, timeout_seg=timeout_seg)
    sql_executavel = convert_placeholders(consulta.sql)
    inicio = time.perf_counter()

    conexao_bruta = engine.raw_connection()
    try:
        with conexao_bruta.cursor() as cursor:
            cursor.execute(sql_executavel, ligados)
            colunas = [descricao[0] for descricao in cursor.description] if cursor.description else []
            linhas_brutas = cursor.fetchmany(limite + 1) if colunas else []
    finally:
        conexao_bruta.rollback()
        conexao_bruta.close()

    truncado = len(linhas_brutas) > limite
    linhas = [
        [_normalizar_celula(valor) for valor in linha]
        for linha in linhas_brutas[:limite]
    ]
    duracao = int((time.perf_counter() - inicio) * 1000)

    return ExecResult(
        columns=colunas,
        rows=linhas,
        truncated=truncado,
        duration_ms=duracao,
    )
