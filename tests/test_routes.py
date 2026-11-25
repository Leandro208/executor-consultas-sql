from app.extensions import db
from app.models import Conexao, Consulta, Grupo, Parametro


def test_pagina_inicial(client):
    resposta = client.get("/")
    assert resposta.status_code == 200
    assert b"Executor SQL" in resposta.data


def test_cria_grupo(client, app):
    resposta = client.post(
        "/grupos/nova",
        data={"nome": "Estudantes", "descricao": "Consultas de alunos", "cor": "#ff0000", "ordem": "1"},
        follow_redirects=True,
    )
    assert resposta.status_code == 200
    with app.app_context():
        grupo = Grupo.query.filter_by(nome="Estudantes").first()
        assert grupo is not None
        assert grupo.descricao == "Consultas de alunos"


def _criar_conexao(client, app, nome="Teste"):
    client.post(
        "/conexoes/nova",
        data={
            "nome": nome,
            "host": "localhost",
            "porta": "5432",
            "database": "sigeduc",
            "usuario": "leitor",
            "senha": "segredo",
            "sslmode": "prefer",
            "timeout_seg": "30",
        },
        follow_redirects=True,
    )
    with app.app_context():
        return Conexao.query.filter_by(nome=nome).first().id


def test_cria_consulta_e_detecta_parametros(client, app):
    conexao_id = _criar_conexao(client, app)

    sql = "SELECT * FROM usuarios WHERE id = :user_id AND ano = :ano"
    resposta = client.post(
        "/consultas/nova",
        data={
            "nome": "Usuario por ID",
            "descricao": "",
            "sql": sql,
            "conexao_id": str(conexao_id),
            "grupo_id": "",
            "ativo": "on",
            "p_user_id_rotulo": "ID do usuario",
            "p_user_id_tipo": "numero",
            "p_user_id_obrigatorio": "on",
            "p_user_id_padrao": "1",
            "p_ano_rotulo": "Ano",
            "p_ano_tipo": "numero",
            "p_ano_obrigatorio": "on",
            "p_ano_padrao": "2024",
        },
        follow_redirects=True,
    )
    assert resposta.status_code == 200

    with app.app_context():
        consulta = Consulta.query.filter_by(nome="Usuario por ID").first()
        assert consulta is not None
        nomes = [p.nome for p in consulta.parametros_ordenados]
        assert nomes == ["user_id", "ano"]
        user_id = Parametro.query.filter_by(consulta_id=consulta.id, nome="user_id").one()
        assert user_id.tipo == "numero"
        assert user_id.rotulo == "ID do usuario"


def test_recusa_sql_de_escrita(client, app):
    conexao_id = _criar_conexao(client, app)
    resposta = client.post(
        "/consultas/nova",
        data={
            "nome": "Perigosa",
            "sql": "DELETE FROM usuarios",
            "conexao_id": str(conexao_id),
            "ativo": "on",
        },
        follow_redirects=True,
    )
    assert b"Somente consultas de leitura" in resposta.data
    with app.app_context():
        assert Consulta.query.filter_by(nome="Perigosa").first() is None


def test_pagina_execucao_renderiza(client, app):
    conexao_id = _criar_conexao(client, app)
    client.post(
        "/consultas/nova",
        data={
            "nome": "Simples",
            "sql": "SELECT 1 AS valor WHERE 1 = :x",
            "conexao_id": str(conexao_id),
            "ativo": "on",
            "p_x_rotulo": "X",
            "p_x_tipo": "numero",
            "p_x_obrigatorio": "on",
            "p_x_padrao": "1",
        },
        follow_redirects=True,
    )
    with app.app_context():
        consulta_id = Consulta.query.filter_by(nome="Simples").first().id

    resposta = client.get(f"/consultas/{consulta_id}/executar")
    assert resposta.status_code == 200
    assert b"Limite de linhas" in resposta.data
