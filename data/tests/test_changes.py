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


# ---------------------------------------------------------------- v3: p-valor, BH, sazonal
def test_p_value_is_monotonic_and_bounded():
    ps = [CH.p_value(v) for v in (0.0, 2.0, 5.0, 8.0, 50.0)]
    assert all(0 < p <= 1 for p in ps)
    assert ps == sorted(ps, reverse=True)
    assert ps[0] > 0.9 and ps[-1] < 1e-4


def test_p_value_is_roughly_calibrated_under_the_null():
    """Sem mudança (Poisson, participação estável), P(p < 0,05) fica perto de 5%."""
    rng = np.random.default_rng(7)
    s = _state()
    ps = []
    for _ in range(1500):
        a = CH.assess(rng.poisson(0.004 * s).astype(float), s, L - 1)
        ps.append(a.p_valor)
    frac = float(np.mean(np.array(ps) < 0.05))
    assert 0.01 < frac < 0.10


def test_benjamini_hochberg_known_example():
    p = np.array([0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212, 0.216])
    assert CH.benjamini_hochberg(p, q=0.05).tolist() == [True, True] + [False] * 8
    assert CH.benjamini_hochberg(np.array([])).tolist() == []


def _yearly_event(weeks: int, bump_weeks: range, factor: float) -> tuple[np.ndarray, np.ndarray]:
    """Série municipal com um evento anual próprio (ex.: festa) que o estado não tem."""
    t = np.arange(weeks)
    s = 10000 * (1 + 0.1 * np.sin(t / 4))
    x = 0.004 * s
    for y in range(weeks // CH.YEAR + 1):
        for w in bump_weeks:
            if y * CH.YEAR + w < weeks:
                x[y * CH.YEAR + w] *= factor
    return np.round(x), s


def test_seasonal_model_absorbs_a_recurring_annual_event():
    """Evento anual de 6 semanas (3x): o modelo de participação o trata como mudança; o sazonal,
    que olha o mesmo período do ano anterior, não. (Mecanismo correto, embora o modelo sazonal
    não tenha sido adotado: ver docs/mudancas.md.)"""
    weeks = 2 * CH.YEAR + 20
    x, s = _yearly_event(weeks, range(10, 16), 3.0)
    end = CH.YEAR + 15  # janela monitorada cobre o evento do 2º ano
    assert CH.cusum_detect(x, s, end, "share") is not None
    assert CH.cusum_detect(x, s, end, "sazonal") is None


def test_seasonal_model_needs_a_previous_year():
    x, s = _yearly_event(CH.BASE_WEEKS + CH.MONITOR_WEEKS + 5, range(0), 1.0)
    assert CH.seasonal_factors(x, s, len(x) - 1) is None
    assert CH.cusum_detect(x, s, len(x) - 1, "sazonal") is None


def test_evaluate_real_uses_the_same_series_for_every_method():
    rng = np.random.default_rng(3)
    weeks = 160
    t = np.arange(weeks)
    s = 10000 * (1 + 0.1 * np.sin(t / 4))
    X = np.stack([rng.poisson(0.004 * s) for _ in range(6)], axis=1).astype(float)
    from datetime import date, timedelta

    datas = [date(2022, 1, 3) + timedelta(weeks=i) for i in range(weeks)]
    rows = CH.evaluate_real(X, s, datas, "teste")
    assert rows
    por_par: dict = {}
    for r in rows:
        por_par.setdefault((r["origem"], r["serie"]), set()).add(r["metodo"])
    assert all(v == {"share", "sazonal", "referencia"} for v in por_par.values())
    # verdades futuras são idênticas entre métodos da mesma série/origem
    t1 = {(r["origem"], r["serie"]): r["t1"] for r in rows}
    assert all(r["t1"] == t1[(r["origem"], r["serie"])] for r in rows)


def test_summarize_computes_lift_against_chance():
    rows = [
        {"metodo": "share", "h": 5.0, "direcao": "alta", "t1": 1.5, "t2": 1.5},
        {"metodo": "share", "h": 5.0, "direcao": None, "t1": 1.0, "t2": 1.0},
        {"metodo": "share", "h": 5.0, "direcao": None, "t1": 1.0, "t2": 1.0},
        {"metodo": "share", "h": 5.0, "direcao": None, "t1": 1.0, "t2": 1.0},
    ]
    r = CH.summarize(rows, "geral", lambda _: "todas")[0]
    # 1 sinal confirmado; por acaso 1 de 4 séries teria razão >= 1,1
    assert (
        r["sinais"] == 1 and r["conf_t1"] == 100.0 and r["acaso_t1"] == 25.0 and r["lift_t1"] == 4.0
    )
