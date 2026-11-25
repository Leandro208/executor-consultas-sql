"""Fabrica da aplicacao Flask."""

from __future__ import annotations

from datetime import datetime

from flask import Flask, request

from .config import Config
from .extensions import db


def create_app(config_object: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)

    from .routes.dashboard import bp as dashboard_bp
    from .routes.groups import bp as groups_bp
    from .routes.connections import bp as connections_bp
    from .routes.queries import bp as queries_bp
    from .routes.history import bp as history_bp
    from .routes.settings import bp as settings_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(groups_bp)
    app.register_blueprint(connections_bp)
    app.register_blueprint(queries_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(settings_bp)

    with app.app_context():
        from . import models  # noqa: F401 - registra as tabelas

        db.create_all()
        _semear_configuracoes()

    @app.template_filter("dt")
    def formatar_data(valor: datetime | None, formato: str = "%d/%m/%Y %H:%M") -> str:
        if not valor:
            return "-"
        return valor.strftime(formato)

    @app.context_processor
    def injetar_contexto() -> dict:
        from .models import configuracoes_atuais

        return {
            "usuario_nome": request.cookies.get("executor_usuario", ""),
            "config_global": configuracoes_atuais(),
        }

    return app


def _semear_configuracoes() -> None:
    from .models import Configuracao

    padroes = {
        "limite_padrao": "100",
        "timeout_seg": "30",
        "teto_exportacao": "50000",
    }
    alterado = False
    for chave, valor in padroes.items():
        if db.session.get(Configuracao, chave) is None:
            db.session.add(Configuracao(chave=chave, valor=valor))
            alterado = True
    if alterado:
        db.session.commit()
