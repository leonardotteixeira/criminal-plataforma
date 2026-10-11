"""Dados de referência do IBGE: malha municipal, municípios e população (Censo 2022)."""

import json

import duckdb
import httpx

from . import config as C


def fetch_reference(force: bool = False) -> None:
    ref = C.LAKE / "ref"
    ref.mkdir(parents=True, exist_ok=True)
    geo = ref / "municipios_sp.geojson"
    pop = ref / "municipios_sp.parquet"
    if pop.exists() and geo.exists() and not force:
        return
    with httpx.Client(follow_redirects=True, timeout=120) as http:
        muns = http.get(C.IBGE_MUN_URL).json()
        popj = http.get(C.IBGE_POP_URL).json()
        geo_json = http.get(C.IBGE_MALHA_URL).json()
    population = popj[0]["resultados"][0]["series"]
    pop_by_id = {int(s["localidade"]["id"]): int(s["serie"]["2022"]) for s in population}
    rows = [(m["id"], m["nome"], pop_by_id.get(m["id"])) for m in muns]
    con = duckdb.connect()
    con.execute("CREATE TABLE m (cd_ibge INTEGER, municipio VARCHAR, populacao_2022 BIGINT)")
    con.executemany("INSERT INTO m VALUES (?,?,?)", rows)
    con.execute(f"COPY m TO '{pop.as_posix()}' (FORMAT parquet)")
    # A malha da API v3 usa o código de 7 dígitos em properties.codarea
    for f in geo_json["features"]:
        code = int(f["properties"]["codarea"])
        f["properties"] = {"cd_ibge": code}
    geo.write_text(json.dumps(geo_json))
    n_pop = sum(r[2] is not None for r in rows)
    print(f"referencia IBGE: {len(rows)} municipios, {n_pop} com populacao")


if __name__ == "__main__":
    fetch_reference(force=True)
