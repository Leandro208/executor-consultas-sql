from app.services.sqlparser import (
    convert_placeholders,
    detect_params,
    validate_read_only,
)


def test_detecta_parametros_simples():
    sql = "SELECT * FROM u WHERE u.id = :user_id AND u.ano = :ano"
    assert detect_params(sql) == ["user_id", "ano"]


def test_ignora_literais_comentarios_e_casts():
    sql = (
        "SELECT ':nao', u.criado_em::date FROM u "
        "WHERE u.id = :id -- :ignorado\n AND u.codigo = :codigo"
    )
    assert detect_params(sql) == ["id", "codigo"]


def test_ignora_dollar_quoted():
    sql = "SELECT $$ :dentro $$ AS x FROM u WHERE u.id = :id"
    assert detect_params(sql) == ["id"]


def test_converte_placeholders_preservando_casts():
    sql = "SELECT u.criado_em::date FROM u WHERE u.id = :id AND u.x = :x"
    convertido = convert_placeholders(sql)
    assert "u.criado_em::date" in convertido
    assert "u.id = %(id)s" in convertido
    assert "u.x = %(x)s" in convertido


def test_converte_nao_afeta_strings():
    sql = "SELECT ':id' AS texto, u.id FROM u WHERE u.id = :id"
    convertido = convert_placeholders(sql)
    assert "':id'" in convertido
    assert "u.id = %(id)s" in convertido


def test_valida_select_e_with():
    assert validate_read_only("SELECT 1")[0]
    assert validate_read_only("select * from t;")[0]
    assert validate_read_only("WITH a AS (SELECT 1) SELECT * FROM a")[0]


def test_recusa_escrita_e_multiplos_comandos():
    assert not validate_read_only("INSERT INTO t VALUES (1)")[0]
    assert not validate_read_only("DROP TABLE t")[0]
    assert not validate_read_only("SELECT 1; DELETE FROM t")[0]
    assert not validate_read_only("")[0]
