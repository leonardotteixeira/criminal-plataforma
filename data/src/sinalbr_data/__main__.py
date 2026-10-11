"""CLI: python -m sinalbr_data [bronze|silver|gold|analytics|changes|history|forecast|quality|all]"""

import sys

import duckdb

from . import analytics, bronze, changes, forecast, gold, history, ibge, quality, silver
from . import config as C


def main(step: str = "all") -> None:
    C.LAKE.mkdir(parents=True, exist_ok=True)
    if step in ("bronze", "all"):
        ibge.fetch_reference()
        bronze.run()
    con = duckdb.connect()
    if step in ("silver", "all"):
        silver.build_silver(con)
        print("silver ok")
    if step in ("gold", "all"):
        print("gold:", gold.build_gold(con))
    if step in ("analytics", "all"):
        print("analytics:", analytics.build_anomalies(con))
    if step in ("changes", "all"):
        res = changes.run(con)
        print("changes:", res["sinais"], "sinais")
        for r in res.get("comparacao", []):
            if r["recorte_tipo"] == "geral":
                print(r)
    if step in ("history", "changes", "all"):
        print("historico do radar:", history.build(con))
    if step in ("forecast", "all"):
        res = forecast.run(con)
        print("forecast:", res["origem"], res["celulas"], "celulas")
        for m in res["metricas"]:
            print(m)
    if step in ("quality", "all"):
        rep = quality.build_report(con)
        md = quality.to_markdown(rep)
        (C.REPORTS / "quality.md").write_text(md, encoding="utf-8")
        print(md)
        print("qualidade:", quality.build_tables(con))
        print("execucoes registradas:", quality.record_run(con, step))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "all")
