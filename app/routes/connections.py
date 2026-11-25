"""Gerenciamento de conexoes com bancos PostgreSQL."""

from __future__ import annotations

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from ..crypto import encrypt_password
from ..extensions import db
from ..models import Conexao
from ..services.connections import dispose_connection, test_connection

bp = Blueprint("connections", __name__, url_prefix="/conexoes")


@bp.get("")
def listar():
    conexoes = Conexao.query.order_by(Conexao.nome).all()
    return render_template("connections.html", conexoes=conexoes)


def _preencher(conexao: Conexao, form) -> str | None:
    nome = (form.get("nome") or "").strip()
    host = (form.get("host") or "").strip()
    database = (form.get("database") or "").strip()
    usuario = (form.get("usuario") or "").strip()

    if not all([nome, host, database, usuario]):
        return "Nome, host, banco e usuario sao obrigatorios."

    duplicada = (
        Conexao.query.filter(db.func.lower(Conexao.nome) == nome.lower())
        .filter(Conexao.id != (conexao.id or 0))
        .first()
    )
    if duplicada:
        return "Ja existe uma conexao com esse nome."

    conexao.nome = nome
    conexao.host = host
    conexao.porta = int(form.get("porta") or 5432)
    conexao.database = database
    conexao.usuario = usuario
    conexao.sslmode = (form.get("sslmode") or "prefer").strip()
    conexao.timeout_seg = int(form.get("timeout_seg") or 30)

    senha = form.get("senha")
    if senha:
        conexao.senha_cifrada = encrypt_password(senha)
    elif conexao.id is None:
        conexao.senha_cifrada = ""

    return None


@bp.route("/nova", methods=["GET", "POST"])
def nova():
    conexao = Conexao(porta=5432, sslmode="prefer", timeout_seg=30)
    if request.method == "POST":
        erro = _preencher(conexao, request.form)
        if erro:
            flash(erro, "danger")
            return render_template("connection_form.html", conexao=conexao)
        db.session.add(conexao)
        db.session.commit()
        flash("Conexao criada.", "success")
        return redirect(url_for("connections.listar"))

    return render_template("connection_form.html", conexao=conexao)


@bp.route("/<int:conexao_id>/editar", methods=["GET", "POST"])
def editar(conexao_id: int):
    conexao = db.get_or_404(Conexao, conexao_id)
    if request.method == "POST":
        erro = _preencher(conexao, request.form)
        if erro:
            flash(erro, "danger")
            return render_template("connection_form.html", conexao=conexao)
        db.session.commit()
        dispose_connection(conexao)
        flash("Conexao atualizada.", "success")
        return redirect(url_for("connections.listar"))

    return render_template("connection_form.html", conexao=conexao)


@bp.post("/<int:conexao_id>/remover")
def remover(conexao_id: int):
    conexao = db.get_or_404(Conexao, conexao_id)
    if conexao.total_consultas > 0:
        flash(
            "Esta conexao esta em uso por consultas. Altere as consultas antes de excluir.",
            "danger",
        )
        return redirect(url_for("connections.listar"))

    dispose_connection(conexao)
    db.session.delete(conexao)
    db.session.commit()
    flash("Conexao removida.", "success")
    return redirect(url_for("connections.listar"))


@bp.post("/<int:conexao_id>/testar")
def testar(conexao_id: int):
    conexao = db.get_or_404(Conexao, conexao_id)
    ok, latencia, mensagem = test_connection(conexao)
    return jsonify({"ok": ok, "latencia_ms": latencia, "mensagem": mensagem})
