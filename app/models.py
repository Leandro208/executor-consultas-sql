"""Modelos de metadados (SQLite)."""

from __future__ import annotations

from datetime import datetime, timezone

from .extensions import db


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Conexao(db.Model):
    __tablename__ = "conexoes"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False, unique=True)
    host = db.Column(db.String(255), nullable=False)
    porta = db.Column(db.Integer, nullable=False, default=5432)
    database = db.Column(db.String(120), nullable=False)
    usuario = db.Column(db.String(120), nullable=False)
    senha_cifrada = db.Column(db.Text, nullable=False, default="")
    sslmode = db.Column(db.String(20), nullable=False, default="prefer")
    timeout_seg = db.Column(db.Integer, nullable=False, default=30)
    criado_em = db.Column(db.DateTime, nullable=False, default=utcnow)

    consultas = db.relationship("Consulta", back_populates="conexao", lazy="dynamic")

    @property
    def total_consultas(self) -> int:
        return self.consultas.count()


class Grupo(db.Model):
    __tablename__ = "grupos"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False, unique=True)
    descricao = db.Column(db.String(255), nullable=False, default="")
    cor = db.Column(db.String(20), nullable=False, default="#0d6efd")
    ordem = db.Column(db.Integer, nullable=False, default=0)
    criado_em = db.Column(db.DateTime, nullable=False, default=utcnow)

    consultas = db.relationship(
        "Consulta", back_populates="grupo", lazy="dynamic", order_by="Consulta.nome"
    )

    @property
    def total_consultas(self) -> int:
        return self.consultas.count()


class Consulta(db.Model):
    __tablename__ = "consultas"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(160), nullable=False)
    descricao = db.Column(db.String(400), nullable=False, default="")
    sql = db.Column(db.Text, nullable=False)
    grupo_id = db.Column(db.Integer, db.ForeignKey("grupos.id"), nullable=True)
    conexao_id = db.Column(db.Integer, db.ForeignKey("conexoes.id"), nullable=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=utcnow)
    atualizado_em = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    grupo = db.relationship("Grupo", back_populates="consultas")
    conexao = db.relationship("Conexao", back_populates="consultas")
    parametros = db.relationship(
        "Parametro",
        back_populates="consulta",
        cascade="all, delete-orphan",
        order_by="Parametro.ordem",
    )
    execucoes = db.relationship(
        "Execucao", back_populates="consulta", cascade="all, delete-orphan", lazy="dynamic"
    )

    @property
    def parametros_ordenados(self) -> list["Parametro"]:
        return sorted(self.parametros, key=lambda p: (p.ordem, p.id or 0))


class Parametro(db.Model):
    __tablename__ = "parametros"

    id = db.Column(db.Integer, primary_key=True)
    consulta_id = db.Column(db.Integer, db.ForeignKey("consultas.id"), nullable=False)
    nome = db.Column(db.String(80), nullable=False)
    rotulo = db.Column(db.String(160), nullable=False, default="")
    tipo = db.Column(db.String(20), nullable=False, default="texto")
    obrigatorio = db.Column(db.Boolean, nullable=False, default=True)
    valor_padrao = db.Column(db.String(255), nullable=False, default="")
    ordem = db.Column(db.Integer, nullable=False, default=0)

    consulta = db.relationship("Consulta", back_populates="parametros")

    __table_args__ = (
        db.UniqueConstraint("consulta_id", "nome", name="uq_parametro_consulta_nome"),
    )


class Execucao(db.Model):
    __tablename__ = "execucoes"

    id = db.Column(db.Integer, primary_key=True)
    consulta_id = db.Column(db.Integer, db.ForeignKey("consultas.id"), nullable=False)
    usuario_nome = db.Column(db.String(120), nullable=False, default="anonimo")
    parametros_json = db.Column(db.Text, nullable=False, default="{}")
    limite = db.Column(db.Integer, nullable=False, default=100)
    linhas_retornadas = db.Column(db.Integer, nullable=False, default=0)
    duracao_ms = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default="sucesso")
    erro = db.Column(db.Text, nullable=True)
    ip = db.Column(db.String(60), nullable=False, default="")
    data_hora = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    consulta = db.relationship("Consulta", back_populates="execucoes")

    @property
    def sucesso(self) -> bool:
        return self.status == "sucesso"


class Configuracao(db.Model):
    __tablename__ = "configuracoes"

    chave = db.Column(db.String(80), primary_key=True)
    valor = db.Column(db.String(255), nullable=False, default="")

    @classmethod
    def get(cls, chave: str, padrao: str = "") -> str:
        item = db.session.get(cls, chave)
        return item.valor if item else padrao

    @classmethod
    def get_int(cls, chave: str, padrao: int) -> int:
        try:
            return int(cls.get(chave, str(padrao)))
        except (TypeError, ValueError):
            return padrao

    @classmethod
    def set(cls, chave: str, valor: str) -> None:
        item = db.session.get(cls, chave)
        if item is None:
            item = cls(chave=chave, valor=str(valor))
            db.session.add(item)
        else:
            item.valor = str(valor)


def configuracoes_atuais() -> dict[str, int]:
    """Le os parametros de configuracao com fallback para os padroes."""
    from flask import current_app

    return {
        "limite_padrao": Configuracao.get_int(
            "limite_padrao", current_app.config["DEFAULT_ROW_LIMIT"]
        ),
        "timeout_seg": Configuracao.get_int(
            "timeout_seg", current_app.config["DEFAULT_TIMEOUT_SECONDS"]
        ),
        "teto_exportacao": Configuracao.get_int(
            "teto_exportacao", current_app.config["DEFAULT_EXPORT_LIMIT"]
        ),
    }


__all__ = [
    "Conexao",
    "Grupo",
    "Consulta",
    "Parametro",
    "Execucao",
    "Configuracao",
    "configuracoes_atuais",
    "utcnow",
]
