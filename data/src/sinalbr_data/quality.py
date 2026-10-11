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


def build_tables(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Tabelas de qualidade para a API (definições formais em docs/qualidade-dados.md).

    - qualidade_ano: indicadores por arquivo anual da SSP (ano de registro).
    - qualidade_categoria: indicadores por arquivo x categoria.
    - qualidade_semana: completude das últimas 30 semanas (total estadual vs. mediana das 8
      anteriores): completa >= 85%, parcial >= 10%, residual < 10%.
    - qualidade_etapas: registros em cada etapa do pipeline e o motivo de cada exclusão.
    - execucoes: histórico de execuções (lake/reports/runs.jsonl).
    """
    g = C.GOLD.as_posix()
    s = f"read_parquet('{(C.SILVER / 'occurrences.parquet').as_posix()}')"
    b = f"read_parquet('{(C.BRONZE / 'ssp_*.parquet').as_posix()}')"
    meta = con.execute(f"SELECT dados_ate FROM '{g}/meta.parquet'").fetchone()[0]
    janela = f"data_fato BETWEEN DATE '{C.FIRST_YEAR}-01-01' AND DATE '{meta}'"
    manifest = {}
    if (C.RAW / "manifest.json").exists():
        manifest = json.loads((C.RAW / "manifest.json").read_text(encoding="utf-8"))
    con.execute(
        "CREATE OR REPLACE TEMP TABLE manif (ano INTEGER, tamanho_mb DOUBLE, fonte_modificada VARCHAR)"
    )
    if manifest:
        con.executemany(
            "INSERT INTO manif VALUES (?,?,?)",
            [
                (int(k), round(v["size"] / 1e6, 1), v.get("last_modified"))
                for k, v in manifest.items()
            ],
        )
    pct = lambda cond: f"round(100 * avg(({cond})::INT), 2)"  # noqa: E731
    queries = {
        "qualidade_ano": f"""
            SELECT source_year AS ano, count(*) AS registros,
                   {pct("geo_status = 'valida'")} AS coord_valida_pct,
                   {pct("geo_status = 'ocultado_ou_zero'")} AS coord_zero_pct,
                   {pct("geo_status = 'ausente'")} AS coord_ausente_pct,
                   {pct("geo_status IN ('fora_do_estado', 'fora_do_municipio')")} AS coord_invalida_pct,
                   {pct("hora IS NULL")} AS sem_hora_pct,
                   {pct("data_imputada")} AS data_imputada_pct,
                   {pct("bairro IS NULL")} AS sem_bairro_pct,
                   {pct("tipo_local IS NULL")} AS sem_tipo_local_pct,
                   {pct("categoria = 'outros'")} AS nao_classificado_pct,
                   count(*) FILTER (WHERE NOT ({janela})) AS fora_da_janela,
                   any_value(m.tamanho_mb) AS tamanho_mb, any_value(m.fonte_modificada) AS fonte_modificada
            FROM {s} LEFT JOIN manif m ON m.ano = source_year GROUP BY 1 ORDER BY 1""",
        "qualidade_categoria": f"""
            SELECT source_year AS ano, categoria, count(*) AS registros,
                   {pct("geo_status = 'valida'")} AS coord_valida_pct,
                   {pct("hora IS NULL")} AS sem_hora_pct,
                   {pct("data_imputada")} AS data_imputada_pct
            FROM {s} GROUP BY 1, 2 ORDER BY 1, 2""",
        "qualidade_semana": f"""
            WITH t AS (SELECT semana, sum(n) AS n FROM '{g}/mun_week.parquet' GROUP BY 1),
            r AS (
              SELECT semana, n, list_aggregate(list(n) OVER (ORDER BY semana
                     ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING), 'median') AS mediana_8 FROM t
            )
            SELECT semana, n::INTEGER AS registros, mediana_8,
                   round(n / mediana_8, 3) AS razao,
                   CASE WHEN n >= 0.85 * mediana_8 THEN 'completa'
                        WHEN n >= 0.10 * mediana_8 THEN 'parcial' ELSE 'residual' END AS status
            FROM r ORDER BY semana DESC LIMIT 30""",
        "qualidade_etapas": f"""
            SELECT * FROM (VALUES
              (1, 'bronze', 'Linhas lidas dos XLSX (colunas mínimas, sem endereço e nº do BO)',
                  (SELECT count(*) FROM {b})),
              (2, 'silver', 'Linhas tipadas e classificadas (nenhuma linha é descartada aqui)',
                  (SELECT count(*) FROM {s})),
              (3, 'gold_municipio', 'Fato dentro da janela {C.FIRST_YEAR} até a data dos dados (séries e taxas por município)',
                  (SELECT count(*) FROM {s} WHERE {janela})),
              (4, 'gold_mapa', 'Além disso, coordenada válida e dentro do município (mapa H3)',
                  (SELECT count(*) FROM {s} WHERE {janela} AND h3_8 IS NOT NULL)),
              (5, 'gold_hora', 'Além da janela, hora informada (grade dia × hora)',
                  (SELECT count(*) FROM {s} WHERE {janela} AND hora IS NOT NULL))
            ) t(ordem, etapa, definicao, registros)""",
    }
    counts = {}
    for name, sql in queries.items():
        con.execute(f"COPY ({sql}) TO '{g}/{name}.parquet' (FORMAT parquet)")
        counts[name] = con.execute(f"SELECT count(*) FROM '{g}/{name}.parquet'").fetchone()[0]
    return counts


def record_run(con: duckdb.DuckDBPyConnection, etapas: str) -> int:
    """Acrescenta a execução atual ao histórico (JSONL) e exporta para gold/execucoes.parquet."""
    g = C.GOLD.as_posix()
    meta = con.execute(f"SELECT * FROM '{g}/meta.parquet'").fetchone()
    cols = [d[0] for d in con.description]
    m = dict(zip(cols, meta, strict=True))
    silver = con.execute(
        f"SELECT count(*) FROM read_parquet('{(C.SILVER / 'occurrences.parquet').as_posix()}')"
    ).fetchone()[0]
    run = {
        "processado_em": datetime.now().isoformat(timespec="seconds"),
        "etapas": etapas,
        "fonte_atualizada_em": m.get("fonte_atualizada_em"),
        "dados_ate": str(m.get("dados_ate")),
        "semana_completa_ate": str(m.get("semana_completa_ate")),
        "registros_silver": silver,
    }
    C.REPORTS.mkdir(parents=True, exist_ok=True)
    path = C.REPORTS / "runs.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(run, ensure_ascii=False) + "\n")
    con.execute(
        f"COPY (SELECT * FROM read_json_auto('{path.as_posix()}') ORDER BY processado_em DESC) "
        f"TO '{g}/execucoes.parquet' (FORMAT parquet)"
    )
    return con.execute(f"SELECT count(*) FROM '{g}/execucoes.parquet'").fetchone()[0]


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
