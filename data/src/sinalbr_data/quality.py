"""Relatório de qualidade de dados (JSON + Markdown)."""

import json
from datetime import datetime

import duckdb

from . import config as C


def build_report(con: duckdb.DuckDBPyConnection) -> dict:
    C.REPORTS.mkdir(parents=True, exist_ok=True)
    s = f"read_parquet('{(C.SILVER / 'occurrences.parquet').as_posix()}')"
    rows = con.execute(
        f"""SELECT source_year, count(*) total,
              avg((geo_status='valida')::INT) p_geo_valida,
              avg((geo_status='ocultado_ou_zero')::INT) p_geo_zero,
              avg((geo_status='ausente')::INT) p_geo_ausente,
              avg((geo_status='fora_do_estado')::INT) p_geo_fora_estado,
              avg((geo_status='fora_do_municipio')::INT) p_geo_fora_mun,
              avg((hora IS NULL)::INT) p_sem_hora,
              avg(data_imputada::INT) p_data_imputada,
              avg((cd_ibge IS NULL OR municipio IS NULL)::INT) p_sem_municipio,
              avg((bairro IS NULL)::INT) p_sem_bairro,
              avg((categoria='outros')::INT) p_categoria_outros,
              avg((year(data_fato) < source_year - 1)::INT) p_fato_muito_antigo
            FROM {s} GROUP BY 1 ORDER BY 1"""
    ).fetchall()
    cols = [d[0] for d in con.description]
    per_year = [dict(zip(cols, r, strict=True)) for r in rows]
    cats = con.execute(
        f"SELECT categoria, natureza, count(*) FROM {s} GROUP BY ALL ORDER BY 1, 3 DESC"
    ).fetchall()
    report = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "por_ano_arquivo": per_year,
        "naturezas": [{"categoria": c, "natureza": n, "n": k} for c, n, k in cats],
    }
    (C.REPORTS / "quality.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    return report


def to_markdown(report: dict) -> str:
    pct = lambda v: f"{100 * v:.1f}%"  # noqa: E731
    lines = [
        "# Relatório de qualidade de dados (SSP-SP)",
        "",
        f"Gerado em {report['gerado_em']} a partir dos arquivos oficiais da SSP-SP.",
        "",
        "| Arquivo | Registros | Coord. válida | Coord. 0/ocultada | Sem coord. "
        "| Fora do município | Sem hora | Data imputada | Sem município | Sem bairro |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in report["por_ano_arquivo"]:
        lines.append(
            f"| {r['source_year']} | {r['total']:,} | {pct(r['p_geo_valida'])} | "
            f"{pct(r['p_geo_zero'])} | {pct(r['p_geo_ausente'])} | {pct(r['p_geo_fora_mun'])} | "
            f"{pct(r['p_sem_hora'])} | {pct(r['p_data_imputada'])} | "
            f"{pct(r['p_sem_municipio'])} | {pct(r['p_sem_bairro'])} |"
        )
    return "\n".join(lines) + "\n"
