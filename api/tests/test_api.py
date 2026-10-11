"""Testes da API contra um lake sintético mínimo (determinístico, sem depender dos dados reais)."""

import duckdb
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(tmp_path_factory, monkeypatch_module):
    lake = tmp_path_factory.mktemp("lake")
    (lake / "gold").mkdir()
    (lake / "ref").mkdir()
    con = duckdb.connect()

    def out(sql, path):
        con.execute(f"COPY ({sql}) TO '{(lake / path).as_posix()}' (FORMAT parquet)")

    out(
        """SELECT * FROM (VALUES
          ('88a8100c07fffff','roubo',DATE '2026-05-01',9),
          ('88a8100c07fffff','roubo',DATE '2026-06-01',3),
          ('88a8100c09fffff','roubo',DATE '2026-06-01',2),
          ('88a8100c0bfffff','furto',DATE '2026-06-01',20)) t(h3,categoria,mes,n)""",
        "gold/cell_month.parquet",
    )
    out(
        """SELECT * FROM (VALUES
          (3550308,'São Paulo','roubo',DATE '2026-05-01',900),
          (3550308,'São Paulo','roubo',DATE '2026-06-01',800),
          (3509502,'Campinas','roubo',DATE '2026-06-01',3)
        ) t(cd_ibge,municipio,categoria,mes,n)""",
        "gold/mun_month.parquet",
    )
    out(
        "SELECT 3550308 cd_ibge,'roubo' categoria,DATE '2026-06-22' semana,10 n",
        "gold/mun_week.parquet",
    )
    out(
        "SELECT 3550308 cd_ibge,'roubo' categoria,1 dow,10 hora,12 n",
        "gold/mun_hour_dow.parquet",
    )
    out(
        "SELECT 3550308 cd_ibge,'X' bairro,'roubo' categoria,DATE '2026-06-01' mes,5 n",
        "gold/bairro_month.parquet",
    )
    out("SELECT 'a' h3,'roubo' categoria,DATE '2026-06-22' semana,5 n", "gold/cell_week.parquet")
    out(
        """SELECT * FROM (VALUES (3550308,'São Paulo',11451999),(3509502,'Campinas',1139047))
        t(cd_ibge,municipio,populacao_2022)""",
        "ref/municipios_sp.parquet",
    )
    monkeypatch_module.setenv("SINALBR_LAKE", str(lake))
    from app import main  # importa depois de apontar o lake

    return TestClient(main.app)


@pytest.fixture(scope="module")
def monkeypatch_module():
    from _pytest.monkeypatch import MonkeyPatch

    mp = MonkeyPatch()
    yield mp
    mp.undo()


def test_meta_has_disclaimers_and_k_min(client):
    r = client.get("/v1/meta").json()
    assert r["marca"] == "SinalBR"
    assert r["k_min"] == 5
    assert any("subnotificação" in a for a in r["avisos"])
    assert r["dados_ate"] == "2026-06-28"


def test_heatmap_suppresses_small_cells(client):
    r = client.get("/v1/heatmap/h3", params={"categoria": "roubo", "inicio": "2026-05-01"}).json()
    # célula 1 soma 12 (>=5); célula 2 tem 2 (<5) e deve ser suprimida
    assert [c["n"] for c in r["cells"]] == [12]
    assert r["celulas_suprimidas"] == 1


def test_heatmap_rejects_unknown_category(client):
    assert client.get("/v1/heatmap/h3", params={"categoria": "xyz"}).status_code == 422


def test_municipios_normalizes_by_population_and_suppresses(client):
    r = client.get(
        "/v1/municipios", params={"categoria": "roubo", "inicio": "2026-05-01", "page_size": 5}
    ).json()
    by = {m["cd_ibge"]: m for m in r["items"]}
    assert by[3550308]["ocorrencias"] == 1700
    assert by[3550308]["taxa_100k"] == pytest.approx(14.8, abs=0.1)
    assert by[3509502]["suprimido"] is True and by[3509502]["ocorrencias"] is None
    assert r["total"] == 2


def test_municipios_search_ignores_accents(client):
    r = client.get("/v1/municipios", params={"busca": "sao paulo"}).json()
    assert [m["municipio"] for m in r["items"]] == ["São Paulo"]


def test_series_marks_last_month_partial(client):
    r = client.get("/v1/series", params={"categoria": "roubo"}).json()
    assert r[-1]["parcial"] is True and r[0]["parcial"] is False
