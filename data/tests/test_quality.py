import duckdb

from sinalbr_data import config as C
from sinalbr_data import quality


def _lake(tmp_path, monkeypatch):
    for name in ("SILVER", "BRONZE", "GOLD", "RAW", "REPORTS"):
        d = tmp_path / name.lower()
        d.mkdir()
        monkeypatch.setattr(C, name, d)
    con = duckdb.connect()
    con.execute(
        f"""COPY (SELECT * FROM (VALUES
          (2025, DATE '2025-03-03', false, 10, 3550308, 'São Paulo', 'SE', 'Via Pública', 'ROUBO', 'roubo', 'valida', 1::UBIGINT),
          (2025, DATE '2025-03-04', false, NULL, 3550308, 'São Paulo', NULL, NULL, 'ESTUPRO', 'sexual', 'ocultado_ou_zero', NULL),
          (2025, DATE '2019-01-01', false, 8, 3550308, 'São Paulo', 'SE', NULL, 'FURTO', 'furto', 'ausente', NULL)
        ) t(source_year, data_fato, data_imputada, hora, cd_ibge, municipio, bairro, tipo_local,
            natureza, categoria, geo_status, h3_8))
        TO '{(C.SILVER / "occurrences.parquet").as_posix()}' (FORMAT parquet)"""
    )
    con.execute(
        f"COPY (SELECT 1 AS x FROM range(3)) TO '{(C.BRONZE / 'ssp_2025.parquet').as_posix()}' (FORMAT parquet)"
    )
    con.execute(
        f"""COPY (SELECT DATE '2025-03-09' AS dados_ate, DATE '2025-03-03' AS semana_completa_ate,
                         '2025-03-10' AS fonte_atualizada_em, '2025-03-11T00:00:00' AS processado_em)
            TO '{(C.GOLD / "meta.parquet").as_posix()}' (FORMAT parquet)"""
    )
    con.execute(
        f"""COPY (SELECT 3550308 AS cd_ibge, 'roubo' AS categoria, w::DATE AS semana,
                         CASE WHEN w = DATE '2025-03-03' THEN 1 ELSE 100 END AS n
                  FROM generate_series(DATE '2025-01-06', DATE '2025-03-03', INTERVAL 7 DAY) g(w))
            TO '{(C.GOLD / "mun_week.parquet").as_posix()}' (FORMAT parquet)"""
    )
    return con


def test_quality_tables_have_formal_indicators(tmp_path, monkeypatch):
    con = _lake(tmp_path, monkeypatch)
    counts = quality.build_tables(con)
    assert counts["qualidade_ano"] == 1 and counts["qualidade_etapas"] == 5
    ano = con.execute(f"SELECT * FROM '{(C.GOLD / 'qualidade_ano.parquet').as_posix()}'").fetchone()
    cols = [d[0] for d in con.description]
    r = dict(zip(cols, ano, strict=True))
    assert r["registros"] == 3
    assert abs(r["coord_valida_pct"] - 33.33) < 0.01
    assert r["fora_da_janela"] == 1  # fato de 2019 fica fora das tabelas gold
    assert r["tamanho_mb"] is None  # sem manifesto: indisponível, não zero
    etapas = con.execute(
        f"SELECT etapa, registros FROM '{(C.GOLD / 'qualidade_etapas.parquet').as_posix()}' ORDER BY ordem"
    ).fetchall()
    assert etapas == [
        ("bronze", 3),
        ("silver", 3),
        ("gold_municipio", 2),
        ("gold_mapa", 1),
        ("gold_hora", 1),
    ]


def test_week_status_marks_residual_week(tmp_path, monkeypatch):
    con = _lake(tmp_path, monkeypatch)
    quality.build_tables(con)
    status = con.execute(
        f"SELECT status FROM '{(C.GOLD / 'qualidade_semana.parquet').as_posix()}' ORDER BY semana DESC"
    ).fetchall()
    assert status[0][0] == "residual" and status[1][0] == "completa"


def test_runs_history_appends(tmp_path, monkeypatch):
    con = _lake(tmp_path, monkeypatch)
    assert quality.record_run(con, "quality") == 1
    assert quality.record_run(con, "all") == 2
