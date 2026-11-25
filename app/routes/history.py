"""Historico de execucoes."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from urllib.parse import urlencode

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import Consulta, Execucao

bp = Blueprint("history", __name__, url_prefix="/historico")

POR_PAGINA = 25


@bp.get("")
def listar():
    consulta_id = request.args.get("consulta_id") or ""
    status = request.args.get("status") or ""
    usuario = (request.args.get("usuario") or "").strip()
    data_ini = request.args.get("data_ini") or ""
    data_fim = request.args.get("data_fim") or ""
    pagina = max(1, int(request.args.get("pagina") or 1))

    query = Execucao.query

    if consulta_id.isdigit():
        query = query.filter(Execucao.consulta_id == int(consulta_id))
    if status in {"sucesso", "erro"}:
        query = query.filter(Execucao.status == status)
    if usuario:
        query = query.filter(Execucao.usuario_nome.ilike(f"%{usuario}%"))
    if data_ini:
        try:
            query = query.filter(
                Execucao.data_hora >= datetime.fromisoformat(data_ini)
            )
        except ValueError:
            pass
    if data_fim:
        try:
            fim = datetime.fromisoformat(data_fim) + timedelta(days=1)
            query = query.filter(Execucao.data_hora < fim)
        except ValueError:
            pass

    total = query.count()
    total_paginas = max(1, (total + POR_PAGINA - 1) // POR_PAGINA)
    pagina = min(pagina, total_paginas)

    execucoes = (
        query.order_by(Execucao.data_hora.desc())
        .offset((pagina - 1) * POR_PAGINA)
        .limit(POR_PAGINA)
        .all()
    )

    consultas = Consulta.query.order_by(Consulta.nome).all()

    filtros = {
        "consulta_id": consulta_id,
        "status": status,
        "usuario": usuario,
        "data_ini": data_ini,
        "data_fim": data_fim,
    }

    filtros_qs = urlencode({k: v for k, v in filtros.items() if v})

    return render_template(
        "history.html",
        execucoes=execucoes,
        consultas=consultas,
        total=total,
        pagina=pagina,
        total_paginas=total_paginas,
        filtros=filtros,
        filtros_qs=filtros_qs,
    )


@bp.get("/<int:execucao_id>")
def detalhe(execucao_id: int):
    execucao = db.get_or_404(Execucao, execucao_id)
    try:
        parametros = json.loads(execucao.parametros_json or "{}")
    except json.JSONDecodeError:
        parametros = {}
    return render_template("history_detail.html", execucao=execucao, parametros=parametros)


@bp.get("/<int:execucao_id>/reexecutar")
def reexecutar(execucao_id: int):
    execucao = db.get_or_404(Execucao, execucao_id)
    try:
        parametros = json.loads(execucao.parametros_json or "{}")
    except json.JSONDecodeError:
        parametros = {}

    argumentos = {"consulta_id": execucao.consulta_id}
    for nome, valor in parametros.items():
        argumentos[f"param_{nome}"] = "" if valor is None else str(valor)
    return redirect(url_for("queries.executar_consulta", **argumentos))


@bp.post("/limpar")
def limpar():
    total = Execucao.query.delete()
    db.session.commit()
    flash(f"{total} registro(s) de historico removido(s).", "success")
    return redirect(url_for("history.listar"))
