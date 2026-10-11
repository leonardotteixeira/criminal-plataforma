"""Previsão de risco: ocorrências esperadas nas próximas 4 semanas por hexágono H3 res. 7.

Princípios: baselines simples primeiro; backtest de origem móvel sem vazamento do futuro;
métricas reportadas mesmo quando o modelo não supera o baseline.

O alvo é a contagem de BOs *registrados*, não crime real. Áreas com mais policiamento ou
mais registro tendem a ser "previstas" como de maior risco (viés de feedback). Ver docs/previsao.md.
"""

from datetime import date, timedelta

import duckdb
import numpy as np

from . import config as C

HORIZON = 4  # semanas
RES = 7
CATEGORIAS = ["roubo", "furto", "lesao_corporal"]
MIN_EVENTS_2Y = 60  # células com menos registros em 104 semanas ficam fora (esparsas demais)
TEST_WEEKS = 24  # janela de teste (origens), em semanas
REFIT_EVERY = 4
TOP_FRAC = 0.10
RIDGE = 1.0
FEATURES_OWN = ["l4", "l12", "l26", "l52", "ly", "sin", "cos"]
FEATURES_NB = [*FEATURES_OWN, "nb12"]


# ---------------------------------------------------------------- painel de dados
def build_panel(con: duckdb.DuckDBPyConnection) -> None:
    """Cria a tabela `panel` (célula x crime x semana) com features e alvo, só com passado."""
    con.execute("INSTALL h3 FROM community; LOAD h3;")
    g = C.GOLD.as_posix()
    ok = con.execute(f"SELECT semana_completa_ate FROM '{g}/meta.parquet'").fetchone()[0]
    cats = ",".join(f"'{c}'" for c in CATEGORIAS)
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE c7 AS
        SELECT h3_h3_to_string(h3_cell_to_parent(h3_string_to_h3(h3), {RES})) AS h3,
               categoria, semana, sum(n)::DOUBLE AS n
        FROM '{g}/cell_week.parquet'
        WHERE categoria IN ({cats}) AND semana <= DATE '{ok}'
        GROUP BY ALL;
        CREATE OR REPLACE TEMP TABLE ent AS
        SELECT h3, categoria FROM c7
        WHERE semana > DATE '{ok}' - INTERVAL 728 DAY GROUP BY ALL HAVING sum(n) >= {MIN_EVENTS_2Y};
        CREATE OR REPLACE TEMP TABLE weeks AS
        SELECT unnest(generate_series((SELECT min(semana) FROM c7), DATE '{ok}',
                                      INTERVAL 7 DAY))::DATE AS semana;
        CREATE OR REPLACE TEMP TABLE dense AS
        SELECT e.h3, e.categoria, w.semana, coalesce(c.n, 0) AS n
        FROM ent e CROSS JOIN weeks w LEFT JOIN c7 c USING (h3, categoria, semana);
        CREATE OR REPLACE TEMP TABLE roll AS
        SELECT *,
          sum(n) OVER (PARTITION BY h3, categoria ORDER BY semana ROWS 3 PRECEDING) AS l4,
          sum(n) OVER (PARTITION BY h3, categoria ORDER BY semana ROWS 11 PRECEDING) AS l12,
          sum(n) OVER (PARTITION BY h3, categoria ORDER BY semana ROWS 25 PRECEDING) AS l26,
          sum(n) OVER (PARTITION BY h3, categoria ORDER BY semana ROWS 51 PRECEDING) AS l52
        FROM dense;
        -- vizinhança: soma das últimas 12 semanas nas células vizinhas (anel 1) dentro do painel
        CREATE OR REPLACE TEMP TABLE nbr AS
        SELECT a.h3, a.categoria, a.semana, coalesce(sum(b.l12), 0) AS nb12
        FROM roll a
        LEFT JOIN (
          SELECT h3 AS src, h3_h3_to_string(unnest(list_filter(
            h3_grid_disk(h3_string_to_h3(h3), 1), x -> x != h3_string_to_h3(h3)))) AS dst
          FROM (SELECT DISTINCT h3 FROM ent)
        ) m ON m.src = a.h3
        LEFT JOIN roll b ON b.h3 = m.dst AND b.categoria = a.categoria AND b.semana = a.semana
        GROUP BY ALL;
        CREATE OR REPLACE TEMP TABLE panel AS
        SELECT r.h3, r.categoria, r.semana, r.l4, r.l12, r.l26, r.l52, n.nb12,
          lag(r.l4, 48) OVER w AS ly,
          lead(r.l4, {HORIZON}) OVER w AS y,
          sin(2 * pi() * (week(r.semana + INTERVAL {HORIZON // 2 * 7} DAY)) / 52.0) AS sin,
          cos(2 * pi() * (week(r.semana + INTERVAL {HORIZON // 2 * 7} DAY)) / 52.0) AS cos
        FROM roll r JOIN nbr n USING (h3, categoria, semana)
        WHERE r.semana >= (SELECT min(semana) FROM weeks) + INTERVAL 52 WEEK
        WINDOW w AS (PARTITION BY r.h3, r.categoria ORDER BY r.semana)
        """
    )


# ---------------------------------------------------------------- modelo
def fit_poisson(X: np.ndarray, y: np.ndarray, ridge: float = RIDGE, iters: int = 30) -> np.ndarray:
    """GLM de Poisson (link log) por IRLS com ridge. X já inclui o intercepto na coluna 0."""
    beta = np.zeros(X.shape[1])
    beta[0] = np.log(max(y.mean(), 1e-3))
    pen = np.eye(X.shape[1]) * ridge
    pen[0, 0] = 0.0
    for _ in range(iters):
        eta = np.clip(X @ beta, -20, 8)
        mu = np.exp(eta)
        z = eta + (y - mu) / mu
        XtW = X.T * mu
        new = np.linalg.solve(XtW @ X + pen, XtW @ z)
        if np.max(np.abs(new - beta)) < 1e-7:
            beta = new
            break
        beta = new
    return beta


def design(d: dict, feats: list[str], stats: tuple | None = None):
    cols = []
    for f in feats:
        v = d[f].astype(float)
        cols.append(v if f in ("sin", "cos") else np.log1p(v))
    M = np.column_stack(cols)
    if stats is None:
        stats = (M.mean(0), M.std(0) + 1e-9)
    M = (M - stats[0]) / stats[1]
    return np.column_stack([np.ones(len(M)), M]), stats


def predict(d: dict, feats: list[str], beta: np.ndarray, stats) -> np.ndarray:
    X, _ = design(d, feats, stats)
    return np.exp(np.clip(X @ beta, -20, 8))


def poisson_deviance(y: np.ndarray, mu: np.ndarray) -> float:
    mu = np.maximum(mu, 0.05)
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(y > 0, y * np.log(y / mu), 0.0)
    return float(np.mean(2 * (t - (y - mu))))


def capture_rate(
    y: np.ndarray, mu: np.ndarray, groups: np.ndarray, frac: float = TOP_FRAC
) -> float:
    """Em cada origem, fração dos eventos reais que caem nas `frac` células de maior previsão."""
    num = den = 0.0
    for g in np.unique(groups):
        m = groups == g
        k = max(1, int(round(frac * m.sum())))
        top = np.argsort(-mu[m], kind="stable")[:k]
        num += y[m][top].sum()
        den += y[m].sum()
    return num / den if den else float("nan")


def capture_by_origin(y: np.ndarray, mu: np.ndarray, groups: np.ndarray) -> np.ndarray:
    return np.array(
        [
            capture_rate(y[groups == g], mu[groups == g], groups[groups == g])
            for g in np.unique(groups)
        ]
    )


def _slice(d: dict, mask: np.ndarray) -> dict:
    return {k: v[mask] for k, v in d.items()}


def backtest(data: dict, cat: str) -> tuple[list[dict], dict]:
    """Origem móvel: para cada bloco de teste, ajusta só com origens cujo alvo já terminou."""
    sem = data["semana_i"]  # inteiro de semanas
    known = ~np.isnan(data["y"])
    last = sem[known].max()
    first_test = last - TEST_WEEKS + 1
    preds = {
        k: np.full(len(sem), np.nan)
        for k in ("persistencia", "media12", "sazonal", "glm", "glm_viz")
    }
    for start in range(first_test, last + 1, REFIT_EVERY):
        end = min(start + REFIT_EVERY - 1, last)
        train = known & (sem + HORIZON <= start) & ~np.isnan(data["ly"])
        test = known & (sem >= start) & (sem <= end)
        if train.sum() < 500 or not test.any():
            continue
        tr, te = _slice(data, train), _slice(data, test)
        for name, feats in (("glm", FEATURES_OWN), ("glm_viz", FEATURES_NB)):
            X, st = design(tr, feats)
            beta = fit_poisson(X, tr["y"])
            preds[name][test] = predict(te, feats, beta, st)
        preds["persistencia"][test] = te["l4"]
        preds["media12"][test] = te["l12"] / 3.0
        preds["sazonal"][test] = np.where(np.isnan(te["ly"]), te["l12"] / 3.0, te["ly"])
    test_mask = known & (sem >= first_test) & ~np.isnan(preds["glm"])
    y = data["y"][test_mask]
    groups = sem[test_mask]
    rows = []
    models = {**{k: v[test_mask] for k, v in preds.items()}, "oraculo": y.astype(float)}
    ref = capture_by_origin(y, models["media12"], groups)
    for name, mu in models.items():
        per_origin = capture_by_origin(y, mu, groups)
        rows.append(
            {
                "categoria": cat,
                "modelo": name,
                "desvio_poisson": round(poisson_deviance(y, mu), 4),
                "mae": round(float(np.mean(np.abs(y - mu))), 4),
                "captura_top10": round(float(capture_rate(y, mu, groups)), 4),
                "origens_melhor_que_media12_pct": round(
                    float(np.mean(per_origin > ref + 1e-9)) * 100, 1
                ),
                "n_obs": int(len(y)),
                "n_origens": int(len(np.unique(groups))),
            }
        )
    # calibração do melhor GLM: decis de previsão (agregando todas as origens de teste)
    mu = preds["glm"][test_mask]
    order = np.argsort(mu)
    calib = {
        "categoria": cat,
        "decis": [
            {
                "decil": i + 1,
                "previsto": round(float(mu[idx].mean()), 3),
                "observado": round(float(y[idx].mean()), 3),
            }
            for i, idx in enumerate(np.array_split(order, 10))
        ],
    }
    return rows, calib


# ---------------------------------------------------------------- execução
def _load(con: duckdb.DuckDBPyConnection, cat: str) -> dict:
    d = con.execute(
        "SELECT h3, (semana - DATE '2000-01-03')::INTEGER // 7 AS semana_i, semana::VARCHAR AS semana, "
        "l4, l12, l26, l52, nb12, ly, y, sin, cos FROM panel WHERE categoria = ? ORDER BY semana, h3",
        [cat],
    ).fetchnumpy()
    out = {}
    for k, v in d.items():
        if hasattr(v, "filled"):  # MaskedArray (nulos)
            v = v.astype(float).filled(np.nan) if v.dtype.kind in "fiu" else v.filled("")
        out[k] = v
    return out


def run(con: duckdb.DuckDBPyConnection | None = None) -> dict:
    con = con or duckdb.connect()
    build_panel(con)
    ok = con.execute(
        f"SELECT semana_completa_ate FROM '{(C.GOLD / 'meta.parquet').as_posix()}'"
    ).fetchone()[0]
    metric_rows, calibs, forecast_rows = [], [], []
    for cat in CATEGORIAS:
        data = _load(con, cat)
        rows, calib = backtest(data, cat)
        metric_rows += rows
        calibs.append(calib)
        # Modelo final: ajusta com todas as origens de alvo conhecido; prevê a partir da última semana.
        known = ~np.isnan(data["y"]) & ~np.isnan(data["ly"])
        tr = _slice(data, known)
        X, st = design(tr, FEATURES_NB)
        beta = fit_poisson(X, tr["y"])
        now = data["semana"] == str(ok)
        cur = _slice(data, now)
        cur["ly"] = np.where(np.isnan(cur["ly"]), cur["l12"] / 3.0, cur["ly"])
        mu = predict(cur, FEATURES_NB, beta, st)
        order = np.argsort(-mu)
        rank = np.empty(len(mu))
        rank[order] = np.arange(len(mu)) / max(len(mu) - 1, 1)
        for h3, m, r in zip(cur["h3"], mu, rank, strict=True):
            faixa = "alta" if r < 0.10 else "media" if r < 0.30 else "baixa"
            forecast_rows.append((h3, cat, round(float(m), 2), round(float(r), 4), faixa))
    out_dir = C.GOLD
    con.execute(
        "CREATE OR REPLACE TEMP TABLE fc (h3 VARCHAR, categoria VARCHAR, esperado_4s DOUBLE, "
        "percentil DOUBLE, faixa VARCHAR)"
    )
    con.executemany("INSERT INTO fc VALUES (?,?,?,?,?)", forecast_rows)
    origem = date.fromisoformat(str(ok))
    con.execute(
        f"COPY (SELECT *, DATE '{origem}' AS origem, DATE '{origem + timedelta(days=7)}' AS inicio_previsao, "
        f"DATE '{origem + timedelta(days=7 * HORIZON + 6)}' AS fim_previsao FROM fc) "
        f"TO '{(out_dir / 'previsao.parquet').as_posix()}' (FORMAT parquet)"
    )
    con.execute(
        "CREATE OR REPLACE TEMP TABLE bt (categoria VARCHAR, modelo VARCHAR, desvio_poisson DOUBLE, "
        "mae DOUBLE, captura_top10 DOUBLE, origens_melhor_que_media12_pct DOUBLE, "
        "n_obs BIGINT, n_origens BIGINT)"
    )
    con.executemany(
        "INSERT INTO bt VALUES (?,?,?,?,?,?,?,?)", [tuple(r.values()) for r in metric_rows]
    )
    con.execute(f"COPY bt TO '{(out_dir / 'backtest.parquet').as_posix()}' (FORMAT parquet)")
    cal = [
        (c["categoria"], d["decil"], d["previsto"], d["observado"])
        for c in calibs
        for d in c["decis"]
    ]
    con.execute(
        "CREATE OR REPLACE TEMP TABLE cal (categoria VARCHAR, decil INT, previsto DOUBLE, observado DOUBLE)"
    )
    con.executemany("INSERT INTO cal VALUES (?,?,?,?)", cal)
    con.execute(
        f"COPY cal TO '{(out_dir / 'backtest_calibracao.parquet').as_posix()}' (FORMAT parquet)"
    )
    return {"origem": str(ok), "celulas": len(forecast_rows), "metricas": metric_rows}
