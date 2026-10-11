import duckdb

from sinalbr_data import analytics
from sinalbr_data import config as C


def test_spike_is_flagged_and_flat_series_is_not(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "GOLD", tmp_path)
    con = duckdb.connect()
    con.execute(
        f"""COPY (
          SELECT 1111111 AS cd_ibge, 'roubo' AS categoria, w::DATE AS semana,
                 CASE WHEN w = DATE '2026-03-02' THEN 60 ELSE 6 + (hash(w) % 3)::INTEGER END AS n
          FROM generate_series(DATE '2025-06-02', DATE '2026-06-29', INTERVAL 7 DAY) g(w)
        ) TO '{(tmp_path / "mun_week.parquet").as_posix()}' (FORMAT parquet)"""
    )
    con.execute(
        f"""COPY (SELECT '88a8100c07fffff' AS h3, 'roubo' AS categoria,
                         DATE '2026-03-02' AS semana, 1 AS n)
            TO '{(tmp_path / "cell_week.parquet").as_posix()}' (FORMAT parquet)"""
    )
    res = analytics.build_anomalies(con)
    rows = con.execute(
        f"SELECT semana, n, z FROM '{(tmp_path / 'anomalias.parquet').as_posix()}'"
        " WHERE nivel = 'municipio'"
    ).fetchall()
    assert [str(r[0]) for r in rows] == ["2026-03-02"]
    assert rows[0][2] >= analytics.Z_MIN
    assert res["semana_completa_ate"] <= "2026-06-29"
