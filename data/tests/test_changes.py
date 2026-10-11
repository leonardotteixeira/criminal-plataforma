import numpy as np

from sinalbr_data import changes as CH

L = CH.BASE_WEEKS + CH.MONITOR_WEEKS


def _state(trend: float = 0.0) -> np.ndarray:
    """Série estadual com sazonalidade e tendência opcional (variação total no período)."""
    t = np.arange(L)
    return 10000 * (1 + 0.1 * np.sin(t / 4)) * (1 + trend * t / L)


def test_step_increase_is_detected_with_start_and_magnitude():
    s = _state()
    x = 0.004 * s  # ~40/semana, participação estável
    change = CH.BASE_WEEKS + 3
    x[change:] *= 1.6
    sig = CH.cusum_detect(np.round(x), s, L - 1)
    assert sig is not None and sig.direcao == "alta"
    assert abs(sig.inicio - change) <= 2
    assert 1.4 < sig.razao < 1.8


def test_stable_share_gives_no_signal():
    rng = np.random.default_rng(3)
    s = _state()
    false = sum(
        CH.cusum_detect(rng.poisson(0.004 * s).astype(float), s, L - 1) is not None
        for _ in range(200)
    )
    assert false / 200 < 0.05


def test_statewide_trend_is_not_a_local_change_but_fools_the_naive_reference():
    """Queda de 40% em todo o estado: o modelo de participação não sinaliza; a referência sim."""
    s = _state(trend=-0.6)
    x = np.round(0.004 * s)
    assert CH.cusum_detect(x, s, L - 1) is None
    assert CH.naive_detect(x, L - 1) == "queda"


def test_isolated_spike_is_not_persistent():
    s = _state()
    x = np.round(0.004 * s)
    x[L - 6] *= 4  # pico de uma semana
    assert CH.cusum_detect(x, s, L - 1) is None


def test_low_volume_series_is_not_evaluated():
    s = _state()
    x = np.round(0.0001 * s)  # ~1/semana
    assert CH._baseline(x, s, L - 1) is None
    assert CH.cusum_detect(x, s, L - 1) is None


def test_detector_only_uses_data_up_to_the_origin():
    """Alterar semanas posteriores à origem não muda o resultado (sem vazamento)."""
    s = np.concatenate([_state(), _state()[:8]])
    x = np.round(0.004 * s)
    x[CH.BASE_WEEKS + 3 : L] *= 1.6
    a = CH.cusum_detect(x.copy(), s, L - 1)
    y = x.copy()
    y[L:] = 0
    b = CH.cusum_detect(y, s, L - 1)
    assert a == b


def test_retrospective_reports_confirmation_against_chance():
    rng = np.random.default_rng(0)
    weeks = 120
    t = np.arange(weeks)
    s = 10000 * (1 + 0.1 * np.sin(t / 4))
    X = np.stack([rng.poisson(0.004 * s) for _ in range(20)], axis=1).astype(float)
    X[60:, :5] *= 1.8  # cinco municípios mudam de patamar e permanecem
    r = CH.retrospective(X, s, weeks - 1)
    assert r["series_avaliadas"] > 0 and r["cusum_sinais"] > 0
    assert r["cusum_confirmados_pct"] > r["cusum_confirmacao_acaso_pct"]
