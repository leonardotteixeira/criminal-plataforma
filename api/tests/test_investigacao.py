"""Histórico no radar, controle de falsas descobertas, decomposição e robustez."""


def test_radar_excludes_signals_that_fail_fdr(client):
    r = client.get("/v1/radar").json()
    mud = {i["categoria"] for i in r["itens"] if i["tipo"] == "mudanca_persistente"}
    assert "drogas" not in mud  # fdr_ok = false
    assert "furto" in mud


def test_radar_items_carry_history_and_ended_list(client):
    r = client.get("/v1/radar").json()
    assert r["historico_disponivel"] is True
    furto = next(
        i for i in r["itens"] if i["tipo"] == "mudanca_persistente" and i["categoria"] == "furto"
    )
    h = furto["historico"]
    assert h["status"] == "persistente" and h["deteccoes"] == 2 and h["reconstruido"] is True
    assert [p["valor"] for p in h["serie"]] == [1.4, 1.5]
    enc = r["deixaram_de_ser_detectados"]
    assert [(e["municipio"], e["direcao"]) for e in enc] == [("Campinas", "queda")]


def test_mudancas_exposes_method_version_and_p_values(client):
    r = client.get("/v1/mudancas").json()
    assert r["metodo_versao"] == "share+bh-K0.5-H5.0"
    assert {i["categoria"]: i["fdr_ok"] for i in r["itens"]}["drogas"] is False


def test_decomposition_by_category_adds_up(client):
    d = client.get("/v1/decomposicao", params={"por": "categoria", "cd_ibge": 3509502}).json()
    assert d["regiao"] == "Campinas"
    soma = sum(i["variacao_abs"] for i in d["itens"])
    assert soma == d["total_atual"] - d["total_anterior"]
    assert abs(sum(i["contribuicao_pct"] for i in d["itens"]) - 100) < 0.5
    assert "não por que" in d["nota"]


def test_decomposition_by_municipality_rules(client):
    assert client.get("/v1/decomposicao", params={"por": "municipio"}).status_code == 422
    r = client.get(
        "/v1/decomposicao", params={"por": "municipio", "categoria": "drogas", "cd_ibge": 1}
    )
    assert r.status_code == 422
    d = client.get(
        "/v1/decomposicao", params={"por": "municipio", "categoria": "drogas", "top": 3}
    ).json()
    assert {i["nome"] for i in d["itens"]} == {"São Paulo", "Campinas"}  # 'demais' exige 2+ membros
    assert sum(i["variacao_abs"] for i in d["itens"]) == d["total_atual"] - d["total_anterior"]


def test_decomposition_omits_items_below_k_and_counts_them(client):
    d = client.get(
        "/v1/decomposicao", params={"por": "categoria", "cd_ibge": 3509502, "meses": 3}
    ).json()
    assert all(i["anterior"] >= 5 and i["atual"] >= 5 for i in d["itens"])
    assert d["total_anterior"] == sum(i["anterior"] for i in d["itens"])  # agregação consistente


def test_robustness_consistent_for_steady_growth(client):
    r = client.get("/v1/robustez", params={"categoria": "furto", "cd_ibge": 3550308}).json()
    assert r["veredito"] == "consistente"
    nomes = [v["nome"] for v in r["verificacoes"]]
    assert nomes == ["janela_6m", "janela_12m", "janela_24m", "mesmo_trimestre_ano_anterior",
                     "incerteza_12m", "relativo_ao_estado"]  # fmt: skip
    assert "não indica causa" in r["resumo"]


def test_robustness_partial_when_change_already_happened(client):
    """Campinas/drogas cai de 400 para 100 em jun/2025 e fica estável: 12m = queda, 6m = estável."""
    r = client.get("/v1/robustez", params={"categoria": "drogas", "cd_ibge": 3509502}).json()
    por = {v["nome"]: v for v in r["verificacoes"]}
    assert por["janela_12m"]["direcao"] == "queda" and por["janela_6m"]["direcao"] == "estavel"
    assert r["veredito"] == "parcialmente_consistente" and "novo patamar" in r["resumo"]


def test_robustness_insufficient_and_validation(client):
    r = client.get("/v1/robustez", params={"categoria": "homicidio", "cd_ibge": 3509502}).json()
    assert r["veredito"] == "insuficiente"
    assert client.get("/v1/robustez", params={"categoria": "xyz"}).status_code == 422
    assert (
        client.get("/v1/robustez", params={"categoria": "roubo", "cd_ibge": 1}).status_code == 404
    )
