import csv
import io
import json

from app.services.exporter import exportar
from app.services.executor import ExecResult


def _resultado():
    return ExecResult(
        columns=["id", "nome", "total"],
        rows=[[1, "Ana", 10], [2, "Bruno", 20]],
        truncated=False,
        duration_ms=5,
    )


def test_csv():
    conteudo, mimetype, extensao = exportar(_resultado(), "csv")
    assert mimetype == "text/csv"
    assert extensao == ".csv"
    texto = conteudo.decode("utf-8-sig")
    linhas = list(csv.reader(io.StringIO(texto), delimiter=";"))
    assert linhas[0] == ["id", "nome", "total"]
    assert linhas[1] == ["1", "Ana", "10"]


def test_json():
    conteudo, mimetype, extensao = exportar(_resultado(), "json")
    assert mimetype == "application/json"
    dados = json.loads(conteudo)
    assert dados[0]["nome"] == "Ana"
    assert dados[1]["total"] == 20


def test_xlsx():
    conteudo, mimetype, extensao = exportar(_resultado(), "xlsx")
    assert extensao == ".xlsx"
    assert conteudo[:2] == b"PK"  # assinatura de zip/xlsx


def test_colunas_duplicadas():
    resultado = ExecResult(columns=["id", "id"], rows=[[1, 2]], duration_ms=1)
    conteudo, _, _ = exportar(resultado, "json")
    dados = json.loads(conteudo)
    assert set(dados[0].keys()) == {"id", "id_2"}
