"""Análises pré-calculadas: detecção de anomalias semanais (município e H3 res. 7).

Método (simples e auditável): para cada entidade x crime, compara a contagem da semana com a
mediana das 12 semanas anteriores. Escala robusta = max(1,4826*MAD, sqrt(mediana)), ou seja,
nunca menor que o ruído de Poisson. Sinaliza z >= Z_MIN, contagem mínima e razão >= 1,3.

Limitações: não modela sazonalidade anual nem feriados; os meses recentes sofrem atraso de
registro, então só semanas "completas" são avaliadas (ver `semana_completa_ate`).
"""

import json
from datetime import datetime
from email.utils import parsedate_to_datetime

import duckdb

from . import config as C

Z_MIN = 3.0
MIN_N = 10
MIN_RATIO = 1.3
BASELINE_WEEKS = 12
LOOKBACK_WEEKS = 26
H3_ANOM_RES = 7  # ~5 km²: células res. 8 são esparsas demais para séries semanais estáveis


def _anomaly_sql(nivel: str, id_expr: str, source: str, min_total: int) -> str:
    return f"""
    WITH ent AS (
      SELECT {id_expr} AS id, categoria, semana, sum(n) AS n FROM {source} GROUP BY ALL
    ),
    keep AS (
      SELECT id, categoria FROM ent WHERE semana > (SELECT max_ok FROM wk) - INTERVAL 364 DAY
      GROUP BY ALL HAVING sum(n) >= {min_total}
    ),
    grid AS (
      SELECT k.id, k.categoria, w.semana FROM keep k CROSS JOIN weeks w
    ),
    dense AS (
      SELECT g.id, g.categoria, g.semana, coalesce(e.n, 0) AS n
      FROM grid g LEFT JOIN ent e USING (id, categoria, semana)
    ),
    base AS (
      SELECT *, list(n) OVER w AS hist FROM dense
      WINDOW w AS (PARTITION BY id, categoria ORDER BY semana
                   ROWS BETWEEN {BASELINE_WEEKS} PRECEDING AND 1 PRECEDING)
    ),
    scored AS (
      SELECT id, categoria, semana, n,
             list_aggregate(hist, 'median') AS med,
             list_aggregate(list_transform(hist, x -> abs(x - list_aggregate(hist, 'median'))),
                            'median') AS mad,
             len(hist) AS n_hist
      FROM base
    )
    SELECT '{nivel}' AS nivel, id, categoria, semana, n,
           round(med, 1) AS esperado,
           round((n - med) / greatest(1.4826 * mad, sqrt(greatest(med, 1))), 2) AS z,
           round(n / greatest(med, 1), 2) AS razao
    FROM scored
    WHERE n_hist = {BASELINE_WEEKS}
      AND semana > (SELECT max_ok FROM wk) - INTERVAL {LOOKBACK_WEEKS * 7} DAY
      AND semana <= (SELECT max_ok FROM wk)
      AND n >= {MIN_N}
      AND (n - med) / greatest(1.4826 * mad, sqrt(greatest(med, 1))) >= {Z_MIN}
      AND n / greatest(med, 1) >= {MIN_RATIO}
    """


def _versao_dados() -> tuple[str | None, str]:
    """(Last-Modified mais recente entre os arquivos da SSP, momento do processamento)."""
    fonte = None
    manifest = C.RAW / "manifest.json"
    if manifest.exists():
        datas = [
            parsedate_to_datetime(m["last_modified"])
            for m in json.loads(manifest.read_text(encoding="utf-8")).values()
            if m.get("last_modified")
        ]
        if datas:
            fonte = max(datas).date().isoformat()
    return fonte, datetime.now().isoformat(timespec="seconds")


def build_anomalies(con: duckdb.DuckDBPyConnection) -> dict:
    con.execute("INSTALL h3 FROM community; LOAD h3;")
    g = C.GOLD.as_posix()
    con.execute(f"CREATE OR REPLACE VIEW mun_week AS SELECT * FROM '{g}/mun_week.parquet'")
    con.execute(
        f"""CREATE OR REPLACE VIEW cell7_week AS
        SELECT h3_h3_to_string(h3_cell_to_parent(h3_string_to_h3(h3), {H3_ANOM_RES})) AS h3,
               categoria, semana, sum(n) AS n
        FROM '{g}/cell_week.parquet' GROUP BY ALL"""
    )
    # Última semana completa: total estadual >= 85% da mediana das 8 semanas anteriores.
    con.execute(
        """CREATE OR REPLACE TEMP TABLE wk AS
        WITH t AS (SELECT semana, sum(n) AS n FROM mun_week GROUP BY 1),
        s AS (
          SELECT semana, n, list_aggregate(list(n) OVER (ORDER BY semana
                 ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING), 'median') AS b FROM t
        )
        SELECT max(semana) FILTER (WHERE n >= 0.85 * b) AS max_ok,
               (SELECT min(semana) FROM t) AS min_w,
               -- Última semana com volume não residual (>= 10% da mediana): ignora registros
               -- soltos com data de fato posterior ao corte do arquivo.
               max(semana) FILTER (WHERE n >= 0.10 * b) AS ultima_valida
        FROM s"""
    )
    con.execute(
        """CREATE OR REPLACE TEMP TABLE weeks AS
        SELECT unnest(generate_series(min_w, max_ok, INTERVAL 7 DAY))::DATE AS semana FROM wk"""
    )
    sql = (
        "("
        + _anomaly_sql("municipio", "CAST(cd_ibge AS VARCHAR)", "mun_week", 52)
        + ") UNION ALL ("
        + _anomaly_sql("h3_7", "h3", "cell7_week", 104)
        + ")"
    )
    out = (C.GOLD / "anomalias.parquet").as_posix()
    con.execute(f"COPY ({sql}) TO '{out}' (FORMAT parquet)")
    fonte, processado = _versao_dados()
    con.execute(
        f"""COPY (SELECT max_ok AS semana_completa_ate, ultima_valida + 6 AS dados_ate,
                         {f"'{fonte}'" if fonte else "NULL"}::VARCHAR AS fonte_atualizada_em,
                         '{processado}'::VARCHAR AS processado_em
                  FROM wk)
        TO '{(C.GOLD / "meta.parquet").as_posix()}' (FORMAT parquet)"""
    )
    stats = con.execute(
        f"SELECT nivel, count(*) FROM read_parquet('{out}') GROUP BY 1 ORDER BY 1"
    ).fetchall()
    return {
        "semana_completa_ate": str(con.execute("SELECT max_ok FROM wk").fetchone()[0]),
        "anomalias": dict(stats),
    }
