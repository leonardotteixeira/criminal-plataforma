import numpy as np

from sinalbr_data import forecast as F


def test_poisson_irls_recovers_coefficients():
    rng = np.random.default_rng(0)
    x = rng.normal(size=20000)
    y = rng.poisson(np.exp(0.5 + 0.8 * x))
    beta = F.fit_poisson(np.column_stack([np.ones_like(x), x]), y, ridge=0.0)
    assert abs(beta[0] - 0.5) < 0.05 and abs(beta[1] - 0.8) < 0.05


def test_capture_rate_perfect_and_random_ranking():
    y = np.array([10, 0, 0, 0, 0, 0, 0, 0, 0, 0.0])
    groups = np.zeros(10)
    assert F.capture_rate(y, y, groups) == 1.0
    assert F.capture_rate(y, -y, groups) == 0.0


def test_deviance_zero_for_perfect_prediction_and_positive_otherwise():
    y = np.array([1.0, 4.0, 9.0])
    assert F.poisson_deviance(y, y) < 1e-9
    assert F.poisson_deviance(y, y * 2) > 0


def test_backtest_has_no_future_leakage():
    """Se o nível dos alvos sobe 10x só no período de teste, o modelo não pode antecipar isso."""
    rng = np.random.default_rng(1)
    weeks, cells = 200, 40
    sem = np.repeat(np.arange(weeks), cells)
    n = len(sem)
    y = np.where(sem >= 170, 50.0, 5.0)
    y[sem >= weeks - F.HORIZON] = np.nan  # alvo ainda desconhecido nas últimas origens
    base = 5.0 + rng.normal(0, 0.1, n)
    data = {
        "h3": np.tile(np.arange(cells).astype(str), weeks),
        "semana_i": sem,
        "semana": sem.astype(str),
        "l4": base, "l12": base * 3, "l26": base * 6, "l52": base * 12, "nb12": base,
        "ly": base, "y": y, "sin": np.sin(sem / 8), "cos": np.cos(sem / 8),
    }  # fmt: skip
    rows, _ = F.backtest(data, "teste")
    glm = next(r for r in rows if r["modelo"] == "glm")
    assert glm["mae"] > 30  # previu ~5 onde o real era 50: sem vazamento
