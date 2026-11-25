"""Configuracoes gerais do sistema."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import Configuracao, configuracoes_atuais

bp = Blueprint("settings", __name__, url_prefix="/configuracoes")


@bp.route("", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            limite = int(request.form.get("limite_padrao") or 100)
            timeout = int(request.form.get("timeout_seg") or 30)
            teto = int(request.form.get("teto_exportacao") or 50_000)
            if not (1 <= limite <= 100_000):
                raise ValueError("O limite padrao deve ficar entre 1 e 100000.")
            if not (5 <= timeout <= 3600):
                raise ValueError("O timeout deve ficar entre 5 e 3600 segundos.")
            if not (1 <= teto <= 1_000_000):
                raise ValueError("O teto de exportacao deve ficar entre 1 e 1000000.")
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("settings.index"))

        Configuracao.set("limite_padrao", limite)
        Configuracao.set("timeout_seg", timeout)
        Configuracao.set("teto_exportacao", teto)
        db.session.commit()
        flash("Configuracoes salvas.", "success")
        return redirect(url_for("settings.index"))

    return render_template("settings.html", cfg=configuracoes_atuais())
