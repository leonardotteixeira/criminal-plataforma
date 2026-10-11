from datetime import date

import duckdb

from sinalbr_data import config as C
from sinalbr_data import history as H

O0, O1 = date(2026, 8, 17), date(2026, 7, 20)  # origem atual e anterior
CHAVE = ("2026-10-08", O0, "share+bh-K0.5-H5.0")


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "LAKE", tmp_path)
    monkeypatch.setattr(C, "GOLD", tmp_path / "gold")
    (tmp_path / "gold").mkdir()
    (tmp_path / "history").mkdir()
    return duckdb.connect()


def _snap(
    obs, origem, tipo="mudanca_persistente", direcao="alta", versao=CHAVE[0], metodo=CHAVE[2]
):
    cat, cd = obs
    return (versao, CHAVE[1], metodo, "reconstrucao", origem, H.obs_id(tipo, cat, cd, direcao if tipo != "anomalia" else None),
            tipo, cat, cd, direcao, None, 1.5, 30.0, 20.0, 0.001, 1.5, "t")  # fmt: skip


def _aval(obs, origem):
    return (CHAVE[0], CHAVE[1], CHAVE[2], origem, "mudanca_persistente", obs[0], obs[1])


def test_status_distinguishes_new_persistent_ended_and_insufficient(tmp_path, monkeypatch):
    con = _setup(tmp_path, monkeypatch)
    P, N, INS, D, S = ("furto", 1), ("furto", 2), ("furto", 3), ("furto", 4), ("furto", 5)
    snaps = [
        _snap(P, O0), _snap(P, O1),  # persistente
        _snap(N, O0),  # novo (avaliável antes, não detectado)
        _snap(INS, O0),  # histórico insuficiente (não avaliável antes)
        _snap(D, O1),  # deixou de ser detectado (avaliável agora)
        _snap(S, O1),  # sem avaliação atual
    ]  # fmt: skip
    avals = [_aval(x, o) for x in (P, N, D) for o in (O0, O1)] + [_aval(INS, O0), _aval(S, O1)]
    H._replace_block(con, tmp_path / "history/radar_snapshots.parquet", H.SNAP_COLS, snaps, CHAVE)
    H._replace_block(con, tmp_path / "history/radar_avaliadas.parquet", H.AVAL_COLS, avals, CHAVE)
    H.summarize(con, CHAVE)
    st = dict(
        con.execute(
            f"SELECT cd_ibge, status FROM '{(tmp_path / 'gold/radar_historico.parquet').as_posix()}'"
        ).fetchall()
    )
    assert st == {1: "persistente", 2: "novo", 3: "historico_insuficiente", 4: "deixou_de_ser_detectado",
                  5: "sem_avaliacao_atual"}  # fmt: skip


def test_direction_flip_is_another_observation_and_is_flagged(tmp_path, monkeypatch):
    con = _setup(tmp_path, monkeypatch)
    x = ("roubo", 9)
    snaps = [_snap(x, O0, direcao="queda"), _snap(x, O1, direcao="alta")]
    H._replace_block(con, tmp_path / "history/radar_snapshots.parquet", H.SNAP_COLS, snaps, CHAVE)
    H._replace_block(
        con,
        tmp_path / "history/radar_avaliadas.parquet",
        H.AVAL_COLS,
        [_aval(x, O0), _aval(x, O1)],
        CHAVE,
    )
    H.summarize(con, CHAVE)
    rows = con.execute(
        f"SELECT direcao, status, mudou_direcao FROM '{(tmp_path / 'gold/radar_historico.parquet').as_posix()}' ORDER BY 1"
    ).fetchall()
    assert rows == [("alta", "deixou_de_ser_detectado", True), ("queda", "novo", True)]


def test_anomalies_get_recurrence_not_an_ended_status(tmp_path, monkeypatch):
    con = _setup(tmp_path, monkeypatch)
    a, b = ("furto", 7), ("furto", 8)
    snaps = [
        _snap(a, O0, tipo="anomalia", metodo="anomalia-mediana12"),
        _snap(a, O1, tipo="anomalia", metodo="anomalia-mediana12"),
        _snap(b, O1, tipo="anomalia", metodo="anomalia-mediana12"),
    ]
    H._replace_block(con, tmp_path / "history/radar_snapshots.parquet", H.SNAP_COLS, snaps, CHAVE)
    H._replace_block(
        con,
        tmp_path / "history/radar_avaliadas.parquet",
        H.AVAL_COLS,
        [_aval(("roubo", 1), O0), _aval(("roubo", 1), O1)],
        CHAVE,
    )
    H.summarize(con, CHAVE)
    st = dict(
        con.execute(
            f"SELECT cd_ibge, status FROM '{(tmp_path / 'gold/radar_historico.parquet').as_posix()}'"
        ).fetchall()
    )
    assert st == {7: "recorrente", 8: "anterior"}


def test_replace_block_is_idempotent_and_keeps_other_versions(tmp_path, monkeypatch):
    con = _setup(tmp_path, monkeypatch)
    path = tmp_path / "history/radar_snapshots.parquet"
    rows = [_snap(("furto", 1), O0), _snap(("furto", 1), O1)]
    assert H._replace_block(con, path, H.SNAP_COLS, rows, CHAVE) == 2
    assert H._replace_block(con, path, H.SNAP_COLS, rows, CHAVE) == 2  # mesma chave: não duplica
    outra = ("2026-11-05", date(2026, 9, 14), CHAVE[2])
    novas = [(outra[0], outra[1], *r[2:]) for r in rows]
    assert H._replace_block(con, path, H.SNAP_COLS, novas, outra) == 4  # nova versão: acumula
    assert (
        H._replace_block(con, path, H.SNAP_COLS, rows, CHAVE) == 4
    )  # reprocessar a antiga: substitui
    dup = con.execute(
        f"SELECT count(*) FROM (SELECT versao_dados, obs_id, origem, count(*) c FROM '{path.as_posix()}' GROUP BY ALL HAVING c > 1)"
    ).fetchone()[0]
    assert dup == 0


def test_summary_ignores_other_methods(tmp_path, monkeypatch):
    con = _setup(tmp_path, monkeypatch)
    x = ("furto", 1)
    snaps = [_snap(x, O0), _snap(("furto", 2), O0, metodo="metodo-antigo")]
    H._replace_block(con, tmp_path / "history/radar_snapshots.parquet", H.SNAP_COLS, snaps, CHAVE)
    H._replace_block(
        con, tmp_path / "history/radar_avaliadas.parquet", H.AVAL_COLS, [_aval(x, O0)], CHAVE
    )
    assert H.summarize(con, CHAVE) == 1


def test_obs_id_is_stable_and_ignores_start_date():
    assert (
        H.obs_id("mudanca_persistente", "furto", 3509502, "alta")
        == "mudanca_persistente|furto|3509502|alta"
    )
    assert H.obs_id("anomalia", "furto", 3509502) == "anomalia|furto|3509502"
