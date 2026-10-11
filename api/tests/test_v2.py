"""Testes das funcionalidades da v2: privacidade, radar, mudanças, comparador e qualidade."""

import shutil


def test_cell_rounding_hides_small_differences_between_windows():
    from app.main import arredondar_celula

    assert [arredondar_celula(n) for n in (5, 7, 8, 12, 13, 1010)] == [5, 5, 10, 10, 15, 1010]
    # Janelas que diferem em 3 registros (12 e 9) publicam o mesmo valor: diferença irrecuperável
    assert arredondar_celula(12) - arredondar_celula(9) == 0


def test_municipios_lista_has_all_without_counts(client):
    r = client.get("/v1/municipios/lista").json()
    assert [m["municipio"] for m in r] == ["Campinas", "São Paulo"]
    assert set(r[0]) == {"cd_ibge", "municipio", "populacao_2022"}


def test_anomalias_filter_by_municipio(client):
    q = {"desde": "2026-06-01"}
    assert len(client.get("/v1/anomalias", params={**q, "cd_ibge": 3550308}).json()["itens"]) == 1
    assert client.get("/v1/anomalias", params={**q, "cd_ibge": 3509502}).json()["itens"] == []


def test_radar_types_criteria_and_reliability_gate(client):
    r = client.get("/v1/radar").json()
    assert {i["tipo"] for i in r["itens"]} == {
        "mudanca_persistente",
        "variacao",
        "anomalia",
        "dados",
    }
    assert set(r["criterios"]) == {"mudanca_persistente", "variacao", "anomalia", "dados"}
    mud = [i for i in r["itens"] if i["tipo"] == "mudanca_persistente"]
    # roubo não passa no portão de confiabilidade (20 sinais históricos; 40% vs 30% por acaso)
    assert [m["categoria"] for m in mud] == ["furto"]
    assert "70%" in mud[0]["explicacao"] and "30%" in mud[0]["explicacao"]
    var = {i["municipio"]: i["direcao"] for i in r["itens"] if i["tipo"] == "variacao"}
    # estado caiu ~43%: SP estável fica "acima"; Campinas (-75%) fica "abaixo"
    assert var == {"São Paulo": "alta", "Campinas": "queda"}
    assert r["contagem"]["anomalia"] == 1 and "registros policiais" in r["aviso"]


def test_radar_filters_and_data_items(client):
    r = client.get("/v1/radar", params={"categoria": "furto", "cd_ibge": 3509502}).json()
    assert [i["tipo"] for i in r["itens"]] == ["dados", "dados"]  # semana parcial + cobertura
    assert any("40%" in i["titulo"] for i in r["itens"])
    assert client.get("/v1/radar", params={"categoria": "xyz"}).status_code == 422


def test_mudancas_reports_evaluation_and_simulation(client):
    r = client.get("/v1/mudancas").json()
    by = {a["categoria"]: a for a in r["avaliacao"]}
    assert by["furto"]["confiavel"] is True and by["roubo"]["confiavel"] is False
    assert {i["categoria"]: i["confiavel"] for i in r["itens"]} == {"furto": True, "roubo": False}
    assert r["simulacao"][0]["cenario"] == "alta_30"


def test_perfil_compares_rates_with_interval_and_suppression(client):
    d = client.get(
        "/v1/comparacao/perfil", params=[("cd_ibge", 3550308), ("cd_ibge", 3509502)]
    ).json()
    assert (d["inicio"], d["fim"]) == ("2025-06-01", "2026-05-31")
    assert (d["inicio_anterior"], d["fim_anterior"]) == ("2024-06-01", "2025-05-31")
    camp = {c["categoria"]: c for c in d["municipios"][1]["categorias"]}
    assert camp["drogas"]["n"] == 1200 and camp["drogas"]["variacao_pct"] == -75.0
    assert camp["furto"]["n"] is None  # sem registros: suprimido, não zero
    rz = {x["categoria"]: x for x in d["razoes"]}
    assert rz["drogas"]["ic_inf"] > 1 and "maior" in rz["drogas"]["leitura"]
    assert "furto" not in rz  # sem razão quando um dos lados é < k


def test_perfil_validates_parameters(client):
    assert client.get("/v1/comparacao/perfil", params={"cd_ibge": 1}).status_code == 404
    r = client.get("/v1/comparacao/perfil", params={"cd_ibge": 3550308, "meses": 2})
    assert r.status_code == 422
    seven = [("cd_ibge", 3550308)] * 7
    assert client.get("/v1/comparacao/perfil", params=seven).status_code == 422


def test_qualidade_returns_tables_and_definitions(client):
    d = client.get("/v1/qualidade").json()
    assert d["anos"][0]["tamanho_mb"] is None  # indisponível, não zero
    assert d["semanas"][0]["status"] == "parcial"
    assert [e["etapa"] for e in d["etapas"]] == ["bronze", "silver"]
    assert d["execucoes"][0]["etapas"] == "all" and "indisponivel" in d["definicoes"]


def test_missing_optional_table_returns_explicit_503(client, tmp_path):
    """Sem as tabelas de mudanças o radar responde 503 dizendo qual etapa rodar."""
    from app import db

    lake = tmp_path / "lake"
    shutil.copytree(db.LAKE_DIR, lake)
    for t in ("mudancas", "mudancas_avaliacao"):
        (lake / "gold" / f"{t}.parquet").unlink()
    saved = (db.LAKE_DIR, db._con, set(db._available))
    try:
        db.LAKE_DIR, db._con = lake, None
        db._available.clear()
        r = client.get("/v1/radar")
        assert r.status_code == 503 and "changes" in r.json()["detail"]
        assert client.get("/v1/municipios/lista").status_code == 200  # o resto segue funcionando
    finally:
        db.LAKE_DIR, db._con = saved[0], saved[1]
        db._available.clear()
        db._available.update(saved[2])
