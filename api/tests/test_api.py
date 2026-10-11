"""Testes dos endpoints originais (mapa, municípios, séries, previsão, exportação)."""

import pytest


def test_meta_has_disclaimers_and_k_min(client):
    r = client.get("/v1/meta").json()
    assert r["marca"] == "SinalBR"
    assert r["k_min"] == 5
    assert any("subnotificação" in a for a in r["avisos"])
    assert r["dados_ate"] == "2026-06-28"
    assert r["completo_ate"] == "2026-06-21"
    assert r["fonte_atualizada_em"] == "2026-06-30" and r["arredondamento_celulas"] == 5


def test_heatmap_suppresses_small_cells(client):
    r = client.get("/v1/heatmap/h3", params={"categoria": "roubo", "inicio": "2026-05-01"}).json()
    # célula 1 soma 12 (>=5, publicada arredondada para 10); célula 2 tem 2 (<5) e é suprimida
    assert [c["n"] for c in r["cells"]] == [10]
    assert r["celulas_suprimidas"] == 1 and r["arredondamento"] == 5


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


def test_tendencia_excludes_incomplete_month_and_detects_growth(client):
    r = client.get("/v1/tendencia", params={"categoria": "furto"}).json()
    assert r["suprimido"] is False
    assert r["serie"][-1]["mes"] == "2026-05-01"  # junho ainda incompleto
    assert r["inclinacao_pct_ano"] > 0
    assert r["variacao_12m_pct"] > 0
    assert len(r["sazonalidade"]) == 12


def test_tendencia_suppresses_tiny_series(client):
    r = client.get("/v1/tendencia", params={"categoria": "roubo", "cd_ibge": 3509502}).json()
    assert r["suprimido"] is True and r["serie"] == []


def test_comparacao_periodos(client):
    q = {"categoria": "furto", "inicio_a": "2025-01-01", "fim_a": "2025-12-31",
         "inicio_b": "2026-01-01", "fim_b": "2026-06-30"}  # fmt: skip
    r = client.get("/v1/comparacao/periodos", params=q).json()
    assert r["a"] > 0 and r["b"] > 0 and r["suprimido"] is False
    bad = client.get("/v1/comparacao/periodos", params={**q, "inicio_a": "2026-01-01"})
    assert bad.status_code == 422


def test_comparacao_periodos_suppresses_small_counts(client):
    q = {"categoria": "roubo", "cd_ibge": 3509502, "inicio_a": "2026-06-01",
         "fim_a": "2026-06-30", "inicio_b": "2026-06-01", "fim_b": "2026-06-30"}  # fmt: skip
    assert client.get("/v1/comparacao/periodos", params=q).json()["suprimido"] is True


def test_comparacao_regioes_returns_rate(client):
    r = client.get("/v1/comparacao/regioes", params=[("cd_ibge", 3550308), ("categoria", "furto")])
    item = r.json()[0]
    assert item["taxa_100k"] > 0 and item["serie_taxa_100k"]
    assert client.get("/v1/comparacao/regioes", params={"cd_ibge": 1}).status_code == 404


def test_anomalias_lists_with_names_and_method(client):
    r = client.get("/v1/anomalias", params={"desde": "2026-06-01"}).json()
    assert r["itens"][0]["nome"] == "São Paulo"
    assert "Poisson" in r["metodo"]


def test_previsao_returns_ranked_cells_with_disclaimer(client):
    r = client.get("/v1/previsao/h3", params={"categoria": "roubo"}).json()
    assert [c["faixa"] for c in r["celulas"]] == ["alta", "baixa"]
    assert "viés" in r["aviso"] and r["inicio_previsao"] == "2026-06-22"
    assert client.get("/v1/previsao/h3", params={"categoria": "xyz"}).status_code == 422


def test_backtest_reports_gain_and_ceiling_honestly(client):
    r = client.get("/v1/previsao/backtest", params={"categoria": "roubo"}).json()
    assert r["reducao_desvio_vs_media12_pct"] == 15.0
    assert r["ganho_captura_vs_media12_pp"] == 1.0
    assert r["captura_teto_oraculo"] == 0.4
    assert all(m["modelo"] != "oraculo" for m in r["modelos"])
    assert len(r["calibracao"]) == 10 and "persistentes" in r["leitura"]


def test_export_municipios_csv_has_bom_metadata_and_suppression(client):
    r = client.get(
        "/v1/export/municipios.csv", params={"categoria": "roubo", "inicio": "2026-05-01"}
    )
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    text = r.content.decode("utf-8")
    assert text.startswith("﻿# ") and "suprimidos" in text
    lines = [ln for ln in text.splitlines() if not ln.lstrip("﻿").startswith("#")]
    assert lines[0].startswith("cd_ibge,municipio")
    assert any(ln.startswith("3509502,Campinas,") and ln.endswith("True") for ln in lines)


def test_export_celulas_csv_only_includes_cells_above_k(client):
    r = client.get("/v1/export/celulas.csv", params={"categoria": "roubo", "inicio": "2026-05-01"})
    rows = [ln for ln in r.text.splitlines() if ln and not ln.lstrip("﻿").startswith("#")]
    assert rows[0] == "h3_res8,ocorrencias" and rows[1:] == ["88a8100c07fffff,10"]
