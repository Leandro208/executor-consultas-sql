"""Gerenciamento e execucao de consultas cadastradas."""

from __future__ import annotations

import io
import json
import re
from datetime import datetime

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from ..extensions import db
from ..models import (
    Conexao,
    Consulta,
    Execucao,
    Grupo,
    Parametro,
    configuracoes_atuais,
)
from ..services.exporter import FORMATOS, exportar
from ..services.executor import (
    ConsultaInvalida,
    ParametrosInvalidos,
    detect_params,
    executar,
    parametros_faltantes,
    validar_antes_de_salvar,
)
from ..services.sqlparser import detect_params as _detect

bp = Blueprint("queries", __name__, url_prefix="/consultas")

TIPOS = {"texto", "numero", "data", "booleano"}


def humanizar(nome: str) -> str:
    return re.sub(r"[_\-]+", " ", nome).strip().title()


def _slug(texto: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_\-]+", "_", texto).strip("_")
    return slug.lower() or "consulta"


def _usuario_atual() -> str:
    return (request.cookies.get("executor_usuario") or "anonimo").strip()[:120]


def _limite_do_form() -> int:
    cfg = configuracoes_atuais()
    bruto = request.form.get("limite") or ""
    if bruto == "personalizado":
        bruto = request.form.get("limite_personalizado") or cfg["limite_padrao"]
    try:
        limite = int(bruto)
    except (TypeError, ValueError):
        limite = cfg["limite_padrao"]
    return max(1, min(limite, 100_000))


def _valores_do_form(consulta: Consulta) -> dict[str, str]:
    return {
        p.nome: request.form.get(f"param_{p.nome}", "")
        for p in consulta.parametros_ordenados
    }


def _defs_da_consulta(consulta: Consulta) -> list[dict]:
    return [
        {
            "nome": p.nome,
            "rotulo": p.rotulo,
            "tipo": p.tipo,
            "obrigatorio": p.obrigatorio,
            "valor_padrao": p.valor_padrao,
        }
        for p in consulta.parametros_ordenados
    ]


def _defs_do_form(sql: str) -> list[dict]:
    defs = []
    for nome in detect_params(sql):
        tipo = (request.form.get(f"p_{nome}_tipo") or "texto").strip().lower()
        defs.append(
            {
                "nome": nome,
                "rotulo": (request.form.get(f"p_{nome}_rotulo") or "").strip()
                or humanizar(nome),
                "tipo": tipo if tipo in TIPOS else "texto",
                "obrigatorio": request.form.get(f"p_{nome}_obrigatorio") == "on",
                "valor_padrao": (request.form.get(f"p_{nome}_padrao") or "").strip(),
            }
        )
    return defs


def _salvar_parametros(consulta: Consulta, sql: str) -> None:
    nomes = detect_params(sql)
    existentes = {p.nome: p for p in consulta.parametros}

    for nome, param in list(existentes.items()):
        if nome not in nomes:
            db.session.delete(param)
            existentes.pop(nome)

    for ordem, nome in enumerate(nomes):
        param = existentes.get(nome)
        if param is None:
            param = Parametro(nome=nome, consulta=consulta)
            db.session.add(param)

        param.consulta = consulta
        param.rotulo = (request.form.get(f"p_{nome}_rotulo") or "").strip() or humanizar(nome)
        tipo = (request.form.get(f"p_{nome}_tipo") or "texto").strip().lower()
        param.tipo = tipo if tipo in TIPOS else "texto"
        param.obrigatorio = request.form.get(f"p_{nome}_obrigatorio") == "on"
        param.valor_padrao = (request.form.get(f"p_{nome}_padrao") or "").strip()
        param.ordem = ordem


def _preencher_consulta(consulta: Consulta, form) -> str | None:
    nome = (form.get("nome") or "").strip()
    sql = (form.get("sql") or "").strip()
    conexao_id = form.get("conexao_id")

    if not nome:
        return "Informe o nome da consulta."
    if not sql:
        return "Informe o SQL da consulta."
    if not conexao_id:
        return "Selecione a conexao do banco."

    ok, erro = validar_antes_de_salvar(sql)
    if not ok:
        return erro

    grupo_id = form.get("grupo_id") or ""
    consulta.nome = nome
    consulta.descricao = (form.get("descricao") or "").strip()
    consulta.sql = sql
    consulta.conexao_id = int(conexao_id)
    consulta.grupo_id = int(grupo_id) if grupo_id else None
    consulta.ativo = form.get("ativo") == "on"

    _salvar_parametros(consulta, sql)
    return None


@bp.get("")
def listar():
    busca = (request.args.get("q") or "").strip()
    grupo_id = request.args.get("grupo") or ""
    status = request.args.get("status") or ""

    query = Consulta.query
    if busca:
        termo = f"%{busca}%"
        query = query.filter(
            Consulta.nome.ilike(termo) | Consulta.descricao.ilike(termo) | Consulta.sql.ilike(termo)
        )
    if grupo_id == "sem":
        query = query.filter(Consulta.grupo_id.is_(None))
    elif grupo_id.isdigit():
        query = query.filter(Consulta.grupo_id == int(grupo_id))
    if status == "ativo":
        query = query.filter(Consulta.ativo.is_(True))
    elif status == "inativo":
        query = query.filter(Consulta.ativo.is_(False))

    consultas = query.order_by(Consulta.nome).all()
    grupos = Grupo.query.order_by(Grupo.ordem, Grupo.nome).all()

    return render_template(
        "queries.html",
        consultas=consultas,
        grupos=grupos,
        busca=busca,
        grupo_id=grupo_id,
        status=status,
    )


@bp.route("/nova", methods=["GET", "POST"])
def nova():
    conexoes = Conexao.query.order_by(Conexao.nome).all()
    grupos = Grupo.query.order_by(Grupo.ordem, Grupo.nome).all()
    consulta = Consulta(ativo=True)

    if not conexoes:
        flash("Cadastre uma conexao antes de criar consultas.", "warning")
        return redirect(url_for("connections.nova"))

    if request.method == "POST":
        erro = _preencher_consulta(consulta, request.form)
        if erro:
            flash(erro, "danger")
            return render_template(
                "query_form.html",
                consulta=consulta,
                conexoes=conexoes,
                grupos=grupos,
                param_defs=_defs_do_form(request.form.get("sql", "")),
            )
        db.session.add(consulta)
        db.session.commit()
        flash("Consulta criada.", "success")
        return redirect(url_for("queries.listar"))

    return render_template(
        "query_form.html",
        consulta=consulta,
        conexoes=conexoes,
        grupos=grupos,
        param_defs=[],
    )


@bp.route("/<int:consulta_id>/editar", methods=["GET", "POST"])
def editar(consulta_id: int):
    consulta = db.get_or_404(Consulta, consulta_id)
    conexoes = Conexao.query.order_by(Conexao.nome).all()
    grupos = Grupo.query.order_by(Grupo.ordem, Grupo.nome).all()

    if request.method == "POST":
        erro = _preencher_consulta(consulta, request.form)
        if erro:
            flash(erro, "danger")
            return render_template(
                "query_form.html",
                consulta=consulta,
                conexoes=conexoes,
                grupos=grupos,
                param_defs=_defs_do_form(request.form.get("sql", "")),
            )
        db.session.commit()
        flash("Consulta atualizada.", "success")
        return redirect(url_for("queries.listar"))

    return render_template(
        "query_form.html",
        consulta=consulta,
        conexoes=conexoes,
        grupos=grupos,
        param_defs=_defs_da_consulta(consulta),
    )


@bp.post("/<int:consulta_id>/remover")
def remover(consulta_id: int):
    consulta = db.get_or_404(Consulta, consulta_id)
    db.session.delete(consulta)
    db.session.commit()
    flash("Consulta removida.", "success")
    return redirect(url_for("queries.listar"))


@bp.post("/<int:consulta_id>/duplicar")
def duplicar(consulta_id: int):
    original = db.get_or_404(Consulta, consulta_id)
    copia = Consulta(
        nome=f"Copia de {original.nome}"[:160],
        descricao=original.descricao,
        sql=original.sql,
        grupo_id=original.grupo_id,
        conexao_id=original.conexao_id,
        ativo=False,
    )
    db.session.add(copia)
    db.session.flush()
    for param in original.parametros_ordenados:
        db.session.add(
            Parametro(
                consulta_id=copia.id,
                nome=param.nome,
                rotulo=param.rotulo,
                tipo=param.tipo,
                obrigatorio=param.obrigatorio,
                valor_padrao=param.valor_padrao,
                ordem=param.ordem,
            )
        )
    db.session.commit()
    flash("Consulta duplicada (inativa). Ajuste o nome e ative.", "success")
    return redirect(url_for("queries.editar", consulta_id=copia.id))


@bp.post("/detectar")
def detectar():
    sql = request.form.get("sql") or (request.get_json(silent=True) or {}).get("sql", "")
    nomes = _detect(sql)
    return jsonify(
        {
            "params": [
                {"nome": nome, "rotulo": humanizar(nome), "tipo": "texto"}
                for nome in nomes
            ]
        }
    )


def _contexto_execucao(consulta: Consulta) -> dict:
    cfg = configuracoes_atuais()
    return {
        "consulta": consulta,
        "config_global": cfg,
        "pendentes": parametros_faltantes(consulta),
    }


@bp.route("/<int:consulta_id>/executar", methods=["GET", "POST"])
def executar_consulta(consulta_id: int):
    consulta = db.get_or_404(Consulta, consulta_id)
    cfg = configuracoes_atuais()

    valores = {}
    for parametro in consulta.parametros_ordenados:
        chave = f"param_{parametro.nome}"
        if chave in request.args:
            valores[parametro.nome] = request.args.get(chave, "")
        else:
            valores[parametro.nome] = parametro.valor_padrao
    limite = cfg["limite_padrao"]
    resultado = None
    erro_execucao = None

    if request.method == "POST":
        valores = _valores_do_form(consulta)
        limite = _limite_do_form()
        inicio = datetime.utcnow()

        try:
            resultado = executar(
                consulta,
                valores,
                limite=limite,
                timeout_seg=cfg["timeout_seg"],
                limite_maximo=100_000,
            )
            status = "sucesso"
            mensagem_erro = None
        except (ConsultaInvalida, ParametrosInvalidos) as exc:
            erro_execucao = str(exc)
            status = "erro"
            mensagem_erro = str(exc)
        except Exception as exc:  # noqa: BLE001 - erro do banco exibido ao usuario
            erro_execucao = f"Erro ao executar: {exc}"
            status = "erro"
            mensagem_erro = str(exc)

        execucao = Execucao(
            consulta_id=consulta.id,
            usuario_nome=_usuario_atual(),
            parametros_json=json.dumps(valores, ensure_ascii=False),
            limite=limite,
            linhas_retornadas=resultado.total_linhas if resultado else 0,
            duracao_ms=resultado.duration_ms if resultado else 0,
            status=status,
            erro=mensagem_erro,
            ip=request.remote_addr or "",
            data_hora=inicio,
        )
        db.session.add(execucao)
        db.session.commit()

    contexto = _contexto_execucao(consulta)
    contexto.update(
        {
            "valores": valores,
            "limite": limite,
            "resultado": resultado,
            "erro_execucao": erro_execucao,
        }
    )
    return render_template("query_execute.html", **contexto)


@bp.post("/<int:consulta_id>/exportar/<formato>")
def exportar_consulta(consulta_id: int, formato: str):
    consulta = db.get_or_404(Consulta, consulta_id)
    formato = (formato or "").lower()
    if formato not in FORMATOS:
        flash("Formato de exportacao invalido.", "danger")
        return redirect(url_for("queries.executar_consulta", consulta_id=consulta.id))

    cfg = configuracoes_atuais()
    valores = _valores_do_form(consulta)
    limite = cfg["teto_exportacao"]
    inicio = datetime.utcnow()

    try:
        resultado = executar(
            consulta,
            valores,
            limite=limite,
            timeout_seg=max(cfg["timeout_seg"], 60),
            limite_maximo=limite,
        )
        conteudo, mimetype, extensao = exportar(resultado, formato)
    except Exception as exc:  # noqa: BLE001
        db.session.add(
            Execucao(
                consulta_id=consulta.id,
                usuario_nome=_usuario_atual(),
                parametros_json=json.dumps(valores, ensure_ascii=False),
                limite=limite,
                linhas_retornadas=0,
                duracao_ms=0,
                status="erro",
                erro=str(exc),
                ip=request.remote_addr or "",
                data_hora=inicio,
            )
        )
        db.session.commit()
        flash(f"Falha na exportacao: {exc}", "danger")
        return redirect(url_for("queries.executar_consulta", consulta_id=consulta.id))

    db.session.add(
        Execucao(
            consulta_id=consulta.id,
            usuario_nome=_usuario_atual(),
            parametros_json=json.dumps(valores, ensure_ascii=False),
            limite=limite,
            linhas_retornadas=resultado.total_linhas,
            duracao_ms=resultado.duration_ms,
            status="sucesso",
            erro=None,
            ip=request.remote_addr or "",
            data_hora=inicio,
        )
    )
    db.session.commit()

    nome_arquivo = (
        f"{_slug(consulta.nome)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{extensao}"
    )
    return send_file(
        io.BytesIO(conteudo),
        mimetype=mimetype,
        as_attachment=True,
        download_name=nome_arquivo,
    )
