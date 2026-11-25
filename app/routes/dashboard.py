"""Dashboard inicial e identificacao simples do usuario."""

from __future__ import annotations

from flask import Blueprint, make_response, redirect, render_template, request, url_for

from ..models import Consulta, Grupo

bp = Blueprint("dashboard", __name__)


@bp.get("/")
def index():
    busca = (request.args.get("q") or "").strip()

    grupos = Grupo.query.order_by(Grupo.ordem, Grupo.nome).all()

    consultas_query = Consulta.query.filter(Consulta.ativo.is_(True))
    if busca:
        termo = f"%{busca}%"
        consultas_query = consultas_query.filter(
            (Consulta.nome.ilike(termo))
            | (Consulta.descricao.ilike(termo))
            | (Consulta.sql.ilike(termo))
        )
    consultas = consultas_query.order_by(Consulta.nome).all()

    agrupadas: dict[int | None, list[Consulta]] = {}
    for consulta in consultas:
        agrupadas.setdefault(consulta.grupo_id, []).append(consulta)

    sem_grupo = agrupadas.pop(None, [])

    return render_template(
        "dashboard.html",
        grupos=grupos,
        agrupadas=agrupadas,
        sem_grupo=sem_grupo,
        busca=busca,
        total_consultas=len(consultas),
        nenhum_resultado=bool(busca) and not consultas,
    )


@bp.post("/identidade")
def identidade():
    nome = (request.form.get("usuario_nome") or "").strip()[:120]
    destino = request.form.get("destino") or request.referrer or url_for("dashboard.index")
    resposta = make_response(redirect(destino))
    if nome:
        resposta.set_cookie(
            "executor_usuario", nome, max_age=60 * 60 * 24 * 180, samesite="Lax"
        )
    else:
        resposta.delete_cookie("executor_usuario")
    return resposta
