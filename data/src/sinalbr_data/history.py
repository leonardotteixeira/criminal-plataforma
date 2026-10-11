"""Histórico do Radar: snapshots das observações e estado de cada uma ao longo do tempo.

Por que snapshots: as tabelas gold guardam só a origem atual. Para saber se um sinal é novo,
persiste ou deixou de ser detectado é preciso guardar o que foi detectado em cada origem.

Duas fontes de linhas, sempre identificadas na coluna ``modo``:
- ``reconstrucao``: origens passadas (a cada 4 semanas, últimas 52) recalculadas com os dados e o
  método ATUAIS. Pode diferir do que teria sido detectado na época, porque a SSP revisa os dados.
- ``atualizacao``: a origem atual de cada versão dos dados. Ao longo das atualizações reais da
  base, estas linhas acumulam o histórico "como foi visto".

Idempotência: cada execução é identificada por (versao_dados, semana_completa_ate, metodo).
Rodar de novo com a mesma chave substitui o bloco; outras chaves são preservadas. Linhas de
métodos diferentes nunca se misturam nos resumos.

Arquivos:
- lake/history/radar_snapshots.parquet: observações detectadas (append-only por chave).
- lake/history/radar_avaliadas.parquet: séries avaliáveis por origem (para distinguir "não
  detectado" de "não avaliado").
- gold/radar_historico.parquet: resumo por observação na versão atual (lido pela API).

Estados (só para mudanças persistentes, que têm um conceito de continuidade):
- ``novo``: detectado na origem atual e não na anterior (que era avaliável).
- ``persistente``: detectado na origem atual e na anterior.
- ``historico_insuficiente``: detectado agora, mas a série não era avaliável na origem anterior.
- ``deixou_de_ser_detectado``: detectado na anterior, avaliável agora e não detectado.
  NÃO significa que a situação foi resolvida: só que o critério deixou de ser atendido.
- ``sem_avaliacao_atual``: detectado antes, mas a série não é avaliável agora.
Picos semanais (anomalias) são eventos pontuais: recebem recorrência, não estado de encerramento.
"""

from __future__ import annotations

from datetime import datetime

import duckdb

from . import changes as CH
from . import config as C

HIST_ORIGENS = 14  # origem atual + 13 anteriores, a cada 4 semanas (~52 semanas)
PASSO = 4
ANOM_JANELA_SEMANAS = 4

SNAP_COLS = (
    "versao_dados VARCHAR, semana_completa_ate DATE, metodo VARCHAR, modo VARCHAR, origem DATE, "
    "obs_id VARCHAR, tipo VARCHAR, categoria VARCHAR, cd_ibge INTEGER, direcao VARCHAR, "
    "inicio DATE, razao DOUBLE, observado DOUBLE, esperado DOUBLE, p_valor DOUBLE, "
    "intensidade DOUBLE, gerado_em VARCHAR"
)
AVAL_COLS = (
    "versao_dados VARCHAR, semana_completa_ate DATE, metodo VARCHAR, origem DATE, "
    "tipo VARCHAR, categoria VARCHAR, cd_ibge INTEGER"
)


def obs_id(tipo: str, categoria: str, cd_ibge: int, direcao: str | None = None) -> str:
    """Identificador estável: mesmo município, crime, tipo e direção = mesma observação.

    A data de início estimada NÃO entra no id: ela oscila entre origens para a mesma mudança.
    Inverter a direção cria outra observação (é outro fenômeno).
    """
    partes = [tipo, categoria, str(cd_ibge)] + ([direcao] if direcao else [])
    return "|".join(partes)


def _snapshot_rows(
    con: duckdb.DuckDBPyConnection, chave: tuple, gerado_em: str
) -> tuple[list, list]:
    versao, max_ok, metodo = chave
    snaps, avals = [], []
    for cat in CH.CATEGORIAS:
        X, s, (weeks, muns) = CH._panel(con, cat, max_ok)
        last = len(weeks) - 1
        for k in range(HIST_ORIGENS):
            end = last - k * PASSO
            if end < 0:
                break
            modo = "atualizacao" if k == 0 else "reconstrucao"
            origem = weeks[end]
            for j, a, ok in CH.detect_origin(X, s, end):
                avals.append((versao, max_ok, metodo, origem, "mudanca_persistente", cat, muns[j]))
                if a.sinal and ok:
                    sig = a.sinal
                    snaps.append(
                        (versao, max_ok, metodo, modo, origem,
                         obs_id("mudanca_persistente", cat, muns[j], sig.direcao),
                         "mudanca_persistente", cat, muns[j], sig.direcao, weeks[sig.inicio],
                         round(sig.razao, 4), sig.observado, round(sig.esperado, 2),
                         a.p_valor, round(sig.razao, 4), gerado_em)
                    )  # fmt: skip
    return snaps, avals


def _anomaly_rows(
    con: duckdb.DuckDBPyConnection, chave: tuple, gerado_em: str, origens: list
) -> list:
    """Picos semanais por origem: presentes se sinalizados nas 4 semanas até a origem."""
    versao, max_ok, metodo = chave
    g = C.GOLD.as_posix()
    rows = []
    for k, origem in enumerate(origens):
        modo = "atualizacao" if k == 0 else "reconstrucao"
        for cd, cat, z, n, esp in con.execute(
            f"""SELECT CAST(id AS INTEGER), categoria, max(z), arg_max(n, z), arg_max(esperado, z)
                FROM '{g}/anomalias.parquet'
                WHERE nivel = 'municipio' AND semana <= ? AND semana > ? - INTERVAL {ANOM_JANELA_SEMANAS * 7} DAY
                GROUP BY ALL""",
            [origem, origem],
        ).fetchall():
            rows.append(
                (versao, max_ok, "anomalia-mediana12", modo, origem, obs_id("anomalia", cat, cd), "anomalia",
                 cat, cd, "alta", None, None, float(n), float(esp), None, float(z), gerado_em)
            )  # fmt: skip
    return rows


def _replace_block(con, path, cols: str, rows: list, chave: tuple) -> int:
    """Remove o bloco com a mesma chave e acrescenta as linhas novas (idempotente)."""
    con.execute(f"CREATE OR REPLACE TEMP TABLE novo ({cols})")
    if rows:
        con.executemany(f"INSERT INTO novo VALUES ({','.join('?' * len(rows[0]))})", rows)
    versao, max_ok, _ = chave
    if path.exists():
        con.execute(
            f"""CREATE OR REPLACE TEMP TABLE tudo AS
                SELECT * FROM read_parquet('{path.as_posix()}')
                WHERE NOT (versao_dados IS NOT DISTINCT FROM ? AND semana_completa_ate = ?)
                UNION ALL BY NAME SELECT * FROM novo""",
            [versao, max_ok],
        )
    else:
        con.execute("CREATE OR REPLACE TEMP TABLE tudo AS SELECT * FROM novo")
    con.execute(f"COPY tudo TO '{path.as_posix()}' (FORMAT parquet)")
    return con.execute("SELECT count(*) FROM tudo").fetchone()[0]


def build(con: duckdb.DuckDBPyConnection | None = None) -> dict:
    con = con or duckdb.connect()
    g = C.GOLD.as_posix()
    hist = C.LAKE / "history"
    hist.mkdir(parents=True, exist_ok=True)
    max_ok, versao = con.execute(
        f"SELECT semana_completa_ate, fonte_atualizada_em FROM '{g}/meta.parquet'"
    ).fetchone()
    chave = (versao, max_ok, CH.METODO_VERSAO)
    gerado_em = datetime.now().isoformat(timespec="seconds")

    snaps, avals = _snapshot_rows(con, chave, gerado_em)
    origens = sorted({a[3] for a in avals}, reverse=True)
    snaps += _anomaly_rows(con, chave, gerado_em, origens)
    n_snap = _replace_block(con, hist / "radar_snapshots.parquet", SNAP_COLS, snaps, chave)
    n_aval = _replace_block(con, hist / "radar_avaliadas.parquet", AVAL_COLS, avals, chave)
    n_res = summarize(con, chave)
    return {"snapshots": n_snap, "avaliadas": n_aval, "observacoes": n_res, "origens": len(origens)}


def summarize(con: duckdb.DuckDBPyConnection, chave: tuple) -> int:
    """Resumo por observação para a versão atual (gold/radar_historico.parquet)."""
    hist = (C.LAKE / "history").as_posix()
    versao, max_ok, metodo = chave
    con.execute(
        f"""CREATE OR REPLACE TEMP TABLE s AS
            SELECT * FROM '{hist}/radar_snapshots.parquet'
            WHERE versao_dados IS NOT DISTINCT FROM ? AND semana_completa_ate = ?
              AND metodo IN (?, 'anomalia-mediana12')""",
        [versao, max_ok, metodo],
    )
    con.execute(
        f"""CREATE OR REPLACE TEMP TABLE av AS
            SELECT DISTINCT origem, categoria, cd_ibge FROM '{hist}/radar_avaliadas.parquet'
            WHERE versao_dados IS NOT DISTINCT FROM ? AND semana_completa_ate = ? AND metodo = ?""",
        [versao, max_ok, metodo],
    )
    con.execute(
        """CREATE OR REPLACE TEMP TABLE og AS
           SELECT origem, row_number() OVER (ORDER BY origem DESC) - 1 AS k
           FROM (SELECT DISTINCT origem FROM av)"""
    )
    atual = con.execute("SELECT origem FROM og WHERE k = 0").fetchone()
    anterior = con.execute("SELECT origem FROM og WHERE k = 1").fetchone()
    atual = atual[0] if atual else max_ok
    anterior = anterior[0] if anterior else None
    out = (C.GOLD / "radar_historico.parquet").as_posix()
    con.execute(
        f"""
        COPY (
          WITH obs AS (
            SELECT obs_id, any_value(tipo) AS tipo, any_value(categoria) AS categoria,
                   any_value(cd_ibge) AS cd_ibge, any_value(direcao) AS direcao,
                   min(origem) AS primeira_deteccao, max(origem) AS ultima_deteccao,
                   count(DISTINCT origem) AS deteccoes,
                   bool_or(origem = ?) AS detectado_atual,
                   bool_or(origem IS NOT DISTINCT FROM ?) AS detectado_anterior,
                   list(struct_pack(origem := origem, valor := intensidade) ORDER BY origem) AS serie
            FROM s GROUP BY obs_id
          ),
          aval AS (
            SELECT o.obs_id,
                   count(DISTINCT av.origem) AS origens_avaliadas,
                   bool_or(av.origem = ?) AS avaliavel_atual,
                   bool_or(av.origem IS NOT DISTINCT FROM ?) AS avaliavel_anterior
            FROM obs o LEFT JOIN av ON av.categoria = o.categoria AND av.cd_ibge = o.cd_ibge
            GROUP BY o.obs_id
          ),
          inv AS (  -- a mesma série foi detectada na direção oposta em alguma origem
            SELECT a.obs_id, true AS mudou_direcao FROM obs a JOIN obs b
              ON a.tipo = b.tipo AND a.categoria = b.categoria AND a.cd_ibge = b.cd_ibge
             AND a.direcao <> b.direcao
            GROUP BY a.obs_id
          )
          SELECT o.*, coalesce(av.origens_avaliadas, 0) AS origens_avaliadas,
                 coalesce(inv.mudou_direcao, false) AS mudou_direcao,
                 CASE
                   WHEN o.tipo = 'anomalia' THEN
                     CASE WHEN o.detectado_atual AND o.deteccoes >= 2 THEN 'recorrente'
                          WHEN o.detectado_atual THEN 'novo'
                          ELSE 'anterior' END
                   WHEN o.detectado_atual AND o.detectado_anterior THEN 'persistente'
                   WHEN o.detectado_atual AND coalesce(av.avaliavel_anterior, false) THEN 'novo'
                   WHEN o.detectado_atual THEN 'historico_insuficiente'
                   WHEN o.detectado_anterior AND coalesce(av.avaliavel_atual, false) THEN 'deixou_de_ser_detectado'
                   WHEN o.detectado_anterior THEN 'sem_avaliacao_atual'
                   ELSE 'anterior'
                 END AS status,
                 ?::DATE AS origem_atual, ?::DATE AS origem_anterior,
                 ? AS metodo, ? AS versao_dados
          FROM obs o LEFT JOIN aval av USING (obs_id) LEFT JOIN inv USING (obs_id)
        ) TO '{out}' (FORMAT parquet)""",
        [atual, anterior, atual, anterior, atual, anterior, metodo, versao],
    )
    return con.execute(f"SELECT count(*) FROM '{out}'").fetchone()[0]
