"""Camada gold: agregados anonimizados (H3 / município / bairro x mês x categoria).

Nenhuma tabela gold contém registros individuais. A supressão de células pequenas
(K_MIN) é aplicada na camada de consulta, sobre o total do filtro escolhido.
"""

import duckdb

from . import config as C

GOLD_TABLES = {
    "cell_month": """
        SELECT h3_h3_to_string(h3_8) AS h3, categoria,
               date_trunc('month', data_fato)::DATE AS mes, count(*)::INTEGER AS n
        FROM silver WHERE h3_8 IS NOT NULL AND {period} GROUP BY ALL""",
    "mun_month": """
        SELECT cd_ibge, municipio, categoria,
               date_trunc('month', data_fato)::DATE AS mes, count(*)::INTEGER AS n
        FROM silver WHERE cd_ibge IS NOT NULL AND {period} GROUP BY ALL""",
    "mun_week": """
        SELECT cd_ibge, categoria, date_trunc('week', data_fato)::DATE AS semana,
               count(*)::INTEGER AS n
        FROM silver WHERE cd_ibge IS NOT NULL AND {period} GROUP BY ALL""",
    "mun_hour_dow": """
        SELECT cd_ibge, categoria, dayofweek(data_fato)::INTEGER AS dow, hora,
               count(*)::INTEGER AS n
        FROM silver WHERE cd_ibge IS NOT NULL AND hora IS NOT NULL AND {period} GROUP BY ALL""",
    "bairro_month": """
        SELECT cd_ibge, bairro, categoria,
               date_trunc('month', data_fato)::DATE AS mes, count(*)::INTEGER AS n
        FROM silver WHERE cd_ibge IS NOT NULL AND bairro IS NOT NULL AND {period} GROUP BY ALL""",
    "cell_week": """
        SELECT h3_h3_to_string(h3_8) AS h3, categoria,
               date_trunc('week', data_fato)::DATE AS semana, count(*)::INTEGER AS n
        FROM silver WHERE h3_8 IS NOT NULL AND {period} GROUP BY ALL""",
}


def build_gold(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    C.GOLD.mkdir(parents=True, exist_ok=True)
    con.execute("INSTALL h3 FROM community; LOAD h3;")
    con.execute(
        f"CREATE OR REPLACE VIEW silver AS "
        f"SELECT * FROM read_parquet('{(C.SILVER / 'occurrences.parquet').as_posix()}')"
    )
    # Só fatos ocorridos no período coberto pelas fontes e não no futuro.
    period = f"data_fato >= DATE '{C.FIRST_YEAR}-01-01' AND data_fato <= current_date"
    counts = {}
    for name, sql in GOLD_TABLES.items():
        out = (C.GOLD / f"{name}.parquet").as_posix()
        con.execute(f"COPY ({sql.format(period=period)}) TO '{out}' (FORMAT parquet)")
        counts[name] = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    return counts
