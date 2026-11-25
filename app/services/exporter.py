"""Geracao de arquivos de exportacao (CSV, XLSX, JSON)."""

from __future__ import annotations

import csv
import io
import json

from .executor import ExecResult

FORMATOS = {
    "csv": ("text/csv", ".csv"),
    "xlsx": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsx",
    ),
    "json": ("application/json", ".json"),
}


def _cabecalhos_unicos(columns: list[str]) -> list[str]:
    resultado: list[str] = []
    vistos: dict[str, int] = {}
    for indice, col in enumerate(columns, start=1):
        nome = (col or f"coluna_{indice}").strip() or f"coluna_{indice}"
        if nome in vistos:
            vistos[nome] += 1
            nome = f"{nome}_{vistos[nome]}"
        else:
            vistos[nome] = 1
        resultado.append(nome)
    return resultado


def exportar(resultado: ExecResult, formato: str) -> tuple[bytes, str, str]:
    """Retorna (conteudo, mimetype, extensao)."""
    formato = (formato or "").lower()
    if formato not in FORMATOS:
        raise ValueError("Formato de exportacao invalido.")

    mimetype, extensao = FORMATOS[formato]
    cabecalhos = _cabecalhos_unicos(resultado.columns)

    if formato == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(cabecalhos)
        writer.writerows(resultado.rows)
        return buffer.getvalue().encode("utf-8-sig"), mimetype, extensao

    if formato == "json":
        registros = [dict(zip(cabecalhos, linha)) for linha in resultado.rows]
        conteudo = json.dumps(registros, ensure_ascii=False, indent=2, default=str)
        return conteudo.encode("utf-8"), mimetype, extensao

    # xlsx
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Resultados"

    ws.append(cabecalhos)
    for celula in ws[1]:
        celula.font = Font(bold=True, color="FFFFFF")
        celula.fill = PatternFill("solid", fgColor="0D6EFD")

    for linha in resultado.rows:
        ws.append(linha)

    ws.freeze_panes = "A2"
    for indice, nome in enumerate(cabecalhos, start=1):
        largura = max(
            [len(str(nome))]
            + [len(str(linha[indice - 1])) for linha in resultado.rows[:200] if len(linha) >= indice]
        )
        ws.column_dimensions[get_column_letter(indice)].width = min(
            max(largura + 2, 10), 60
        )

    arquivo = io.BytesIO()
    wb.save(arquivo)
    return arquivo.getvalue(), mimetype, extensao
