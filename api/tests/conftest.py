"""Fixture compartilhado: lake sintético mínimo (determinístico, sem depender dos dados reais)."""

import duckdb
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client(tmp_path_factory, monkeypatch_module):
    lake = tmp_path_factory.mktemp("lake")
    (lake / "gold").mkdir()
    (lake / "ref").mkdir()
    con = duckdb.connect()

    def out(sql, path):
        con.execute(f"COPY ({sql}) TO '{(lake / path).as_posix()}' (FORMAT parquet)")

    out(
        """SELECT * FROM (VALUES
          ('88a8100c07fffff','roubo',DATE '2026-05-01',9),
          ('88a8100c07fffff','roubo',DATE '2026-06-01',3),
          ('88a8100c09fffff','roubo',DATE '2026-06-01',2),
          ('88a8100c0bfffff','furto',DATE '2026-06-01',20)) t(h3,categoria,mes,n)""",
        "gold/cell_month.parquet",
    )
    out(
        """SELECT * FROM (VALUES
          (3550308,'São Paulo','roubo',DATE '2026-05-01',900),
          (3550308,'São Paulo','roubo',DATE '2026-06-01',800),
          (3509502,'Campinas','roubo',DATE '2026-06-01',3)
        ) t(cd_ibge,municipio,categoria,mes,n)""",
        "gold/mun_month.parquet",
    )
    out(
        "SELECT 3550308 cd_ibge,'roubo' categoria,DATE '2026-06-22' semana,10 n",
        "gold/mun_week.parquet",
    )
    out(
        "SELECT 3550308 cd_ibge,'roubo' categoria,1 dow,10 hora,12 n",
        "gold/mun_hour_dow.parquet",
    )
    out(
        "SELECT 3550308 cd_ibge,'X' bairro,'roubo' categoria,DATE '2026-06-01' mes,5 n",
        "gold/bairro_month.parquet",
    )
    out("SELECT 'a' h3,'roubo' categoria,DATE '2026-06-22' semana,5 n", "gold/cell_week.parquet")
    out(
        """SELECT * FROM (VALUES (3550308,'São Paulo',11451999),(3509502,'Campinas',1139047))
        t(cd_ibge,municipio,populacao_2022)""",
        "ref/municipios_sp.parquet",
    )
    out(
        """SELECT 3550308 AS cd_ibge, 'São Paulo' AS municipio, 'furto' AS categoria,
                  m::DATE AS mes, (100 + 2 * row_number() OVER (ORDER BY m))::INTEGER AS n
           FROM generate_series(DATE '2024-01-01', DATE '2026-06-01', INTERVAL 1 MONTH) g(m)""",
        "gold/mun_month_furto.parquet",
    )
    con.execute(
        f"""COPY (SELECT * FROM '{(lake / "gold/mun_month.parquet").as_posix()}'
                  UNION ALL SELECT * FROM '{(lake / "gold/mun_month_furto.parquet").as_posix()}')
            TO '{(lake / "gold/mun_month2.parquet").as_posix()}' (FORMAT parquet)"""
    )
    (lake / "gold/mun_month.parquet").unlink()
    (lake / "gold/mun_month2.parquet").rename(lake / "gold/mun_month.parquet")
    out(
        """SELECT DATE '2026-06-15' AS semana_completa_ate, DATE '2026-06-28' AS dados_ate,
                  '2026-06-30' AS fonte_atualizada_em, '2026-07-01T10:00:00' AS processado_em""",
        "gold/meta.parquet",
    )
    # drogas: SP estável (300/mês) e Campinas caindo de 400 para 100/mês -> estado cai ~43%
    out(
        """SELECT cd_ibge, municipio, 'drogas' AS categoria, m::DATE AS mes,
                  CASE WHEN cd_ibge = 3550308 THEN 300
                       WHEN m < DATE '2025-06-01' THEN 400 ELSE 100 END AS n
           FROM (VALUES (3550308, 'São Paulo'), (3509502, 'Campinas')) v(cd_ibge, municipio)
           CROSS JOIN generate_series(DATE '2024-06-01', DATE '2026-05-01', INTERVAL 1 MONTH) g(m)""",
        "gold/mun_month_drogas.parquet",
    )
    con.execute(
        f"""COPY (SELECT * FROM '{(lake / "gold/mun_month.parquet").as_posix()}'
                  UNION ALL SELECT * FROM '{(lake / "gold/mun_month_drogas.parquet").as_posix()}')
            TO '{(lake / "gold/mun_month3.parquet").as_posix()}' (FORMAT parquet)"""
    )
    (lake / "gold/mun_month.parquet").unlink()
    (lake / "gold/mun_month3.parquet").rename(lake / "gold/mun_month.parquet")
    out(
        """SELECT * FROM (VALUES
          (3550308, 'furto', 'alta', DATE '2026-04-06', 10, 1.5, 300.0, 200.0, 9.0),
          (3550308, 'roubo', 'queda', DATE '2026-04-06', 10, 0.6, 60.0, 100.0, 7.0)
        ) t(cd_ibge, categoria, direcao, inicio, semanas, razao, observado, esperado, cusum_max)
        CROSS JOIN (SELECT DATE '2026-06-15' AS semana_referencia)""",
        "gold/mudancas.parquet",
    )
    out(
        """SELECT * FROM (VALUES
          ('retrospectiva', 'furto', NULL, NULL, 1000.0, 100.0, 70.0, 30.0, 0.1, 75.0, 40.0, NULL, NULL),
          ('retrospectiva', 'roubo', NULL, NULL, 1000.0, 20.0, 40.0, 30.0, 0.02, 60.0, 40.0, NULL, NULL),
          ('simulacao', 'roubo', 'alta_30', 30.0, NULL, NULL, NULL, NULL, 0.72, NULL, NULL, 0.43, 4.2)
        ) t(tipo, categoria, cenario, nivel_semanal, series_avaliadas, cusum_sinais,
            cusum_confirmados_pct, cusum_confirmacao_acaso_pct, cusum_taxa_sinal,
            referencia_confirmados_pct, referencia_confirmacao_acaso_pct, referencia_taxa_sinal,
            cusum_atraso_medio_semanas)""",
        "gold/mudancas_avaliacao.parquet",
    )
    out(
        """SELECT 2026 ano, 1000 registros, 70.0 coord_valida_pct, 18.0 coord_zero_pct,
                  10.0 coord_ausente_pct, 2.0 coord_invalida_pct, 30.0 sem_hora_pct,
                  0.0 data_imputada_pct, 1.0 sem_bairro_pct, 0.0 sem_tipo_local_pct,
                  0.0 nao_classificado_pct, 3 fora_da_janela, NULL::DOUBLE tamanho_mb,
                  NULL::VARCHAR fonte_modificada""",
        "gold/qualidade_ano.parquet",
    )
    out(
        """SELECT * FROM (VALUES (2026, 'furto', 600, 40.0, 43.0, 0.0),
                                (2026, 'roubo', 400, 85.0, 10.0, 0.0))
           t(ano, categoria, registros, coord_valida_pct, sem_hora_pct, data_imputada_pct)""",
        "gold/qualidade_categoria.parquet",
    )
    out(
        """SELECT * FROM (VALUES (DATE '2026-06-22', 50, 100.0, 0.5, 'parcial'),
                                (DATE '2026-06-15', 98, 100.0, 0.98, 'completa'))
           t(semana, registros, mediana_8, razao, status)""",
        "gold/qualidade_semana.parquet",
    )
    out(
        """SELECT * FROM (VALUES (1, 'bronze', 'linhas lidas', 1000), (2, 'silver', 'tipadas', 1000))
           t(ordem, etapa, definicao, registros)""",
        "gold/qualidade_etapas.parquet",
    )
    out(
        """SELECT '2026-07-01T10:00:00' processado_em, 'all' etapas, '2026-06-30' fonte_atualizada_em,
                  '2026-06-28' dados_ate, '2026-06-15' semana_completa_ate, 1000 registros_silver""",
        "gold/execucoes.parquet",
    )
    out(
        """SELECT 'municipio' nivel, '3550308' id, 'furto' categoria, DATE '2026-06-08' semana,
                  50 n, 20.0 esperado, 6.5 z, 2.5 razao""",
        "gold/anomalias.parquet",
    )
    out(
        """SELECT * FROM (VALUES
          ('87a8100c0ffffff','roubo',12.5,0.02,'alta'),
          ('87a8100c1ffffff','roubo',3.1,0.5,'baixa')) t(h3,categoria,esperado_4s,percentil,faixa)
          CROSS JOIN (SELECT DATE '2026-06-15' origem, DATE '2026-06-22' inicio_previsao,
                             DATE '2026-07-19' fim_previsao)""",
        "gold/previsao.parquet",
    )
    out(
        """SELECT * FROM (VALUES
          ('roubo','media12',2.0,4.0,0.38,0.0,100,10),
          ('roubo','glm_viz',1.7,3.8,0.39,60.0,100,10),
          ('roubo','oraculo',0.0,0.0,0.40,100.0,100,10)
        ) t(categoria,modelo,desvio_poisson,mae,captura_top10,origens_melhor_que_media12_pct,
            n_obs,n_origens)""",
        "gold/backtest.parquet",
    )
    out(
        "SELECT 'roubo' categoria, i AS decil, i * 1.0 previsto, i * 1.1 observado "
        "FROM range(1, 11) t(i)",
        "gold/backtest_calibracao.parquet",
    )
    monkeypatch_module.setenv("SINALBR_LAKE", str(lake))
    from app import main  # importa depois de apontar o lake

    return TestClient(main.app)


@pytest.fixture(scope="session")
def monkeypatch_module():
    from _pytest.monkeypatch import MonkeyPatch

    mp = MonkeyPatch()
    yield mp
    mp.undo()
