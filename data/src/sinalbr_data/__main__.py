"""CLI: python -m sinalbr_data [bronze|silver|gold|quality|all]"""

import sys

import duckdb

from . import bronze, gold, ibge, quality, silver
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
    if step in ("quality", "all"):
        rep = quality.build_report(con)
        md = quality.to_markdown(rep)
        (C.REPORTS / "quality.md").write_text(md, encoding="utf-8")
        print(md)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "all")
