"""Controles de divulgação: janelas ancoradas, agregação consistente e supressão de pontos."""


def test_heatmap_only_accepts_anchored_windows(client):
    ok = client.get("/v1/heatmap/h3", params={"inicio": "2026-04-01"})  # 3 meses até jun/2026
    assert ok.status_code == 200
    dois_meses = client.get("/v1/heatmap/h3", params={"inicio": "2026-05-01"})
    assert dois_meses.status_code == 422 and "3, 6, 12, 24" in dois_meses.json()["detail"]
    fim_antigo = client.get("/v1/heatmap/h3", params={"inicio": "2026-01-01", "fim": "2026-03-31"})
    assert (
        fim_antigo.status_code == 422
        and "terminar na data dos dados" in fim_antigo.json()["detail"]
    )
    assert client.get("/v1/export/celulas.csv", params={"inicio": "2026-05-01"}).status_code == 422


def test_heatmap_default_window_is_twelve_months(client):
    r = client.get("/v1/heatmap/h3").json()
    assert (r["inicio"], r["fim"]) == ("2025-07-01", "2026-06-28")


def test_all_crimes_cell_is_sum_of_publishable_categories(client):
    """Célula com furto 20 e roubo 3: 'todos' = 20, não 23 (roubo 3 não é publicável)."""
    todos = {
        c["h3"]: c["n"]
        for c in client.get("/v1/heatmap/h3", params={"inicio": "2026-04-01"}).json()["cells"]
    }
    furto = {
        c["h3"]: c["n"]
        for c in client.get(
            "/v1/heatmap/h3", params={"inicio": "2026-04-01", "categoria": "furto"}
        ).json()["cells"]
    }
    assert todos["88a8100c0bfffff"] == furto["88a8100c0bfffff"] == 20


def test_ranking_total_does_not_reveal_suppressed_category(client):
    """Campinas tem roubo = 3 em jun/2026 (suprimido): o total 'todos' não pode incluí-lo."""
    q = {"inicio": "2026-04-01", "fim": "2026-06-28", "busca": "campinas"}
    todos = client.get("/v1/municipios", params=q).json()["items"][0]["ocorrencias"]
    soma = 0
    for cat in (
        "roubo",
        "furto",
        "homicidio",
        "lesao_corporal",
        "sexual",
        "drogas",
        "armas",
        "transito",
    ):
        item = client.get("/v1/municipios", params={**q, "categoria": cat}).json()["items"][0]
        soma += item["ocorrencias"] or 0
    assert todos == soma  # total - soma das categorias exibidas = 0


def test_comparator_total_is_sum_of_published_categories(client):
    p = client.get("/v1/comparacao/perfil", params={"cd_ibge": 3509502, "meses": 12}).json()[
        "municipios"
    ][0]
    publicadas = sum(c["n"] for c in p["categorias"] if c["n"] is not None)
    assert p["total"] == publicadas


def test_municipal_series_suppresses_small_points_as_null_not_zero(client):
    s = client.get("/v1/series", params={"categoria": "roubo", "cd_ibge": 3509502}).json()
    jun = next(x for x in s if x["periodo"] == "2026-06-01")
    assert jun["n"] is None and jun["suprimido"] is True


def test_trend_hides_small_months_and_dependent_statistics(client):
    t = client.get("/v1/tendencia", params={"categoria": "armas", "cd_ibge": 3509502}).json()
    assert t["meses_suprimidos"] == 1
    dez = next(p for p in t["serie"] if p["mes"] == "2025-12-01")
    assert dez["n"] is None
    # variação e inclinação usariam dez/2025 junto com os meses publicados: não são calculadas
    assert t["variacao_12m_pct"] is None and t["inclinacao_pct_ano"] is None
    assert t["sazonalidade"] == [] and "ocultos" in t["nota"]


def test_hour_grid_distinguishes_suppressed_from_zero(client):
    grid = client.get("/v1/hora-dia", params={"cd_ibge": 3550308, "categoria": "roubo"}).json()
    assert len(grid) == 168
    cel = {(c["dow"], c["hora"]): c["n"] for c in grid}
    assert cel[(1, 10)] == 12 and cel[(0, 0)] == 0
