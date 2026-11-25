"""Gerenciamento de grupos de consultas."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import Consulta, Grupo

bp = Blueprint("groups", __name__, url_prefix="/grupos")


@bp.get("")
def listar():
    grupos = Grupo.query.order_by(Grupo.ordem, Grupo.nome).all()
    return render_template("groups.html", grupos=grupos)


@bp.post("/nova")
def nova():
    nome = (request.form.get("nome") or "").strip()
    if not nome:
        flash("Informe o nome do grupo.", "danger")
        return redirect(url_for("groups.listar"))

    if Grupo.query.filter(db.func.lower(Grupo.nome) == nome.lower()).first():
        flash("Ja existe um grupo com esse nome.", "danger")
        return redirect(url_for("groups.listar"))

    grupo = Grupo(
        nome=nome,
        descricao=(request.form.get("descricao") or "").strip(),
        cor=(request.form.get("cor") or "#0d6efd").strip(),
        ordem=int(request.form.get("ordem") or 0),
    )
    db.session.add(grupo)
    db.session.commit()
    flash(f"Grupo '{grupo.nome}' criado.", "success")
    return redirect(url_for("groups.listar"))


@bp.post("/<int:grupo_id>/editar")
def editar(grupo_id: int):
    grupo = db.get_or_404(Grupo, grupo_id)
    nome = (request.form.get("nome") or "").strip()
    if not nome:
        flash("Informe o nome do grupo.", "danger")
        return redirect(url_for("groups.listar"))

    duplicado = (
        Grupo.query.filter(db.func.lower(Grupo.nome) == nome.lower())
        .filter(Grupo.id != grupo.id)
        .first()
    )
    if duplicado:
        flash("Ja existe outro grupo com esse nome.", "danger")
        return redirect(url_for("groups.listar"))

    grupo.nome = nome
    grupo.descricao = (request.form.get("descricao") or "").strip()
    grupo.cor = (request.form.get("cor") or "#0d6efd").strip()
    grupo.ordem = int(request.form.get("ordem") or 0)
    db.session.commit()
    flash("Grupo atualizado.", "success")
    return redirect(url_for("groups.listar"))


@bp.post("/<int:grupo_id>/remover")
def remover(grupo_id: int):
    grupo = db.get_or_404(Grupo, grupo_id)
    if request.form.get("mover_consultas") == "1":
        Consulta.query.filter_by(grupo_id=grupo.id).update({Consulta.grupo_id: None})
    elif grupo.consultas.count() > 0:
        flash(
            "Este grupo possui consultas. Marque a opcao para move-las para "
            "'Sem grupo' antes de excluir.",
            "danger",
        )
        return redirect(url_for("groups.listar"))

    nome = grupo.nome
    db.session.delete(grupo)
    db.session.commit()
    flash(f"Grupo '{nome}' removido.", "success")
    return redirect(url_for("groups.listar"))
