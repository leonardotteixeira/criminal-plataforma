"""Detector de mudanças persistentes nas séries semanais por município x crime.

Pergunta respondida: "o município passou a registrar, de forma sustentada, mais (ou menos)
ocorrências do que o padrão estadual explicaria?". Não responde por que isso aconteceu.

Método
------
Esperado (modelo de participação): mu_t = p * S_t, onde S_t é o total estadual do crime na
semana t e p é a participação do município nas 26 semanas de linha de base. Isso absorve a
sazonalidade estadual, feriados, o atraso de registro e a tendência estadual (ex.: queda de
roubos em todo o estado não gera sinal em cada município).

Resíduo padronizado: z_t = (x_t - mu_t) / sqrt(phi * mu_t), com phi (superdispersão) estimado
na linha de base (estatística de Pearson, mínimo 1).

CUSUM bilateral nas 12 semanas monitoradas: S+_t = max(0, S+_{t-1} + z_t - K),
S-_t = max(0, S-_{t-1} - z_t - K). Há sinal quando S cruza H. O início estimado da mudança é a
semana seguinte ao último zero antes do cruzamento. "Persistente" exige ao menos 4 semanas
desde o início, magnitude >= 20% e as 4 últimas semanas ainda na mesma direção (>= 10%).

Referência simples (para comparação): razão das últimas 8 semanas sobre a média das 26 da
linha de base, sinalizando |razão - 1| >= 25% com z de Poisson >= 3, sem ajuste estadual.

A avaliação (simulação + retrospectiva em dados reais) é gravada em
gold/mudancas_avaliacao.parquet e documentada em docs/mudancas.md.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb
import numpy as np

from . import config as C

BASE_WEEKS = 26
MONITOR_WEEKS = 12
K = 0.5
H = 5.0
MIN_LEVEL = 3.0  # média esperada mínima por semana na linha de base
MIN_WEEKS = 4
MIN_MAGNITUDE = 0.20
TAIL_WEEKS = 4
TAIL_MIN = 0.10
CONFIRM_WEEKS = 8
CATEGORIAS = [
    "roubo",
    "furto",
    "lesao_corporal",
    "drogas",
    "sexual",
    "homicidio",
    "armas",
    "transito",
]


@dataclass
class Sinal:
    direcao: str  # "alta" | "queda"
    inicio: int  # índice da semana de início estimada
    alarme: int  # índice da semana em que o CUSUM cruzou H
    razao: float  # observado / esperado desde o início
    observado: float
    esperado: float
    cusum_max: float


def _baseline(x: np.ndarray, s: np.ndarray, end: int) -> tuple[float, float, int, int] | None:
    """Participação p, superdispersão phi e limites do monitoramento para a origem `end`."""
    m0 = end - MONITOR_WEEKS + 1
    b0 = m0 - BASE_WEEKS
    if b0 < 0:
        return None
    xb, sb = x[b0:m0], s[b0:m0]
    if sb.sum() <= 0:
        return None
    p = xb.sum() / sb.sum()
    mu_b = p * sb
    if mu_b.mean() < MIN_LEVEL:
        return None
    phi = max(1.0, float(np.sum((xb - mu_b) ** 2 / np.maximum(mu_b, 1e-9)) / (BASE_WEEKS - 1)))
    return p, phi, m0, end


def cusum_detect(x: np.ndarray, s: np.ndarray, end: int) -> Sinal | None:
    """Mudança persistente na janela monitorada que termina em `end` (inclusive)."""
    base = _baseline(x, s, end)
    if base is None:
        return None
    p, phi, m0, _ = base
    mu = p * s[m0 : end + 1]
    xm = x[m0 : end + 1]
    z = (xm - mu) / np.sqrt(phi * np.maximum(mu, 1e-9))
    for direcao, sign in (("alta", 1.0), ("queda", -1.0)):
        cs, last_zero, alarme, cmax = 0.0, -1, None, 0.0
        for i, zi in enumerate(z):
            cs = max(0.0, cs + sign * zi - K)
            cmax = max(cmax, cs)
            if cs == 0.0 and alarme is None:
                last_zero = i
            if cs > H and alarme is None:
                alarme = i
        if alarme is None:
            continue
        ini = last_zero + 1
        obs, esp = float(xm[ini:].sum()), float(mu[ini:].sum())
        razao = obs / esp if esp > 0 else np.inf
        tail = xm[-TAIL_WEEKS:].sum() / max(mu[-TAIL_WEEKS:].sum(), 1e-9)
        dur = len(xm) - ini
        ok_mag = razao >= 1 + MIN_MAGNITUDE if sign > 0 else razao <= 1 - MIN_MAGNITUDE
        ok_tail = tail >= 1 + TAIL_MIN if sign > 0 else tail <= 1 - TAIL_MIN
        if dur >= MIN_WEEKS and ok_mag and ok_tail:
            return Sinal(direcao, m0 + ini, m0 + alarme, razao, obs, esp, cmax)
    return None


def naive_detect(x: np.ndarray, end: int) -> str | None:
    """Referência: últimas 8 semanas vs média da linha de base, sem ajuste estadual."""
    m0 = end - MONITOR_WEEKS + 1
    b0 = m0 - BASE_WEEKS
    if b0 < 0:
        return None
    lam = x[b0:m0].mean()
    if lam < MIN_LEVEL:
        return None
    obs = x[end - 7 : end + 1].sum()
    esp = 8 * lam
    z = (obs - esp) / np.sqrt(esp)
    if obs / esp >= 1.25 and z >= 3:
        return "alta"
    if obs / esp <= 0.75 and z <= -3:
        return "queda"
    return None


# ---------------------------------------------------------------- dados reais
def _panel(con: duckdb.DuckDBPyConnection, cat: str, max_ok) -> tuple[np.ndarray, np.ndarray, list]:
    """Matriz semanas x municípios (densa, zeros onde não há registro) e série estadual."""
    g = C.GOLD.as_posix()
    weeks = [
        r[0]
        for r in con.execute(
            f"SELECT DISTINCT semana FROM '{g}/mun_week.parquet' WHERE semana <= ? ORDER BY 1",
            [max_ok],
        ).fetchall()
    ]
    idx = {w: i for i, w in enumerate(weeks)}
    rows = con.execute(
        f"SELECT cd_ibge, semana, n FROM '{g}/mun_week.parquet' WHERE categoria = ? AND semana <= ?",
        [cat, max_ok],
    ).fetchall()
    muns = sorted({r[0] for r in rows})
    col = {m: j for j, m in enumerate(muns)}
    X = np.zeros((len(weeks), len(muns)))
    for m, w, n in rows:
        X[idx[w], col[m]] = n
    return X, X.sum(axis=1), [weeks, muns]


def _sim_series(rng, lam: float, s: np.ndarray, phi: float, step: float, start: int) -> np.ndarray:
    mean = lam * s / s[:BASE_WEEKS].mean()
    mean = mean * np.where(np.arange(len(s)) >= start, step, 1.0)
    # Binomial negativa com variância phi * mean (gama-Poisson)
    shape = mean / max(phi - 1, 1e-6)
    lam_t = rng.gamma(shape, (phi - 1) / 1.0) if phi > 1 else mean
    return rng.poisson(lam_t).astype(float)


def simulate(s_real: np.ndarray, n_sims: int = 400, seed: int = 0) -> list[dict]:
    """Falsos alarmes e atraso com a forma real da série estadual (sazonalidade e tendência)."""
    rng = np.random.default_rng(seed)
    L = BASE_WEEKS + MONITOR_WEEKS
    out = []
    starts = np.arange(0, len(s_real) - L)
    for lam in (3.0, 10.0, 30.0):
        for step, nome in (
            (1.0, "sem_mudanca"),
            (1.3, "alta_30"),
            (1.5, "alta_50"),
            (0.7, "queda_30"),
        ):
            alarms_c = alarms_n = 0
            delays = []
            for _ in range(n_sims):
                o = int(rng.choice(starts))
                s = s_real[o : o + L].astype(float)
                change_at = BASE_WEEKS + 3  # mudança na 4ª semana monitorada
                x = _sim_series(rng, lam, s, 1.5, step, change_at)
                sig = cusum_detect(x, s, L - 1)
                want = None if step == 1.0 else ("alta" if step > 1 else "queda")
                if sig and (want is None or sig.direcao == want):
                    alarms_c += 1
                    if want:
                        delays.append(sig.alarme - change_at)
                nv = naive_detect(x, L - 1)
                if nv and (want is None or nv == want):
                    alarms_n += 1
            out.append(
                {
                    "nivel_semanal": lam,
                    "cenario": nome,
                    "cusum_taxa_sinal": round(alarms_c / n_sims, 4),
                    "referencia_taxa_sinal": round(alarms_n / n_sims, 4),
                    "cusum_atraso_medio_semanas": round(float(np.mean(delays)), 2)
                    if delays
                    else None,
                }
            )
    return out


def retrospective(X: np.ndarray, s: np.ndarray, last: int) -> dict:
    """Origens a cada 4 semanas no histórico: taxa de sinais e confirmação fora da amostra.

    Confirmado = nas 8 semanas seguintes ao fim da janela, a razão observado/esperado continua
    >= 1,1 (alta) ou <= 0,9 (queda). Para o CUSUM o esperado é o modelo de participação; para a
    referência, a média da linha de base (cada método é avaliado pela própria definição).

    A taxa base é a chance de "confirmar" por acaso: a fração de TODAS as séries avaliadas cuja
    razão futura cai na mesma faixa, ponderada pelas direções dos sinais. Confirmação próxima da
    taxa base indicaria que o sinal não carrega informação.
    """
    first = BASE_WEEKS + MONITOR_WEEKS - 1
    sig_c: list[tuple[str, bool]] = []
    sig_n: list[tuple[str, bool]] = []
    fut_c: list[float] = []
    fut_n: list[float] = []
    series = 0
    for end in range(first, last - CONFIRM_WEEKS + 1, 4):
        fut = slice(end + 1, end + 1 + CONFIRM_WEEKS)
        for j in range(X.shape[1]):
            x = X[:, j]
            base = _baseline(x, s, end)
            if base is None:
                continue
            series += 1
            p, _, m0, _ = base
            r_c = x[fut].sum() / max(p * s[fut].sum(), 1e-9)
            r_n = x[fut].sum() / max(CONFIRM_WEEKS * x[m0 - BASE_WEEKS : m0].mean(), 1e-9)
            fut_c.append(r_c)
            fut_n.append(r_n)
            sig = cusum_detect(x, s, end)
            if sig:
                sig_c.append((sig.direcao, r_c >= 1.1 if sig.direcao == "alta" else r_c <= 0.9))
            nv = naive_detect(x, end)
            if nv:
                sig_n.append((nv, r_n >= 1.1 if nv == "alta" else r_n <= 0.9))

    def resumo(sigs: list[tuple[str, bool]], futs: list[float]) -> tuple:
        if not sigs:
            return None, None
        f = np.asarray(futs)
        base_up, base_down = float(np.mean(f >= 1.1)), float(np.mean(f <= 0.9))
        conf = 100 * np.mean([ok for _, ok in sigs])
        base = 100 * np.mean([base_up if d == "alta" else base_down for d, _ in sigs])
        return round(float(conf), 1), round(float(base), 1)

    cc, cb = resumo(sig_c, fut_c)
    nc, nb = resumo(sig_n, fut_n)
    return {
        "series_avaliadas": series,
        "cusum_sinais": len(sig_c),
        "cusum_taxa_sinal": round(len(sig_c) / series, 4) if series else None,
        "cusum_confirmados_pct": cc,
        "cusum_confirmacao_acaso_pct": cb,
        "referencia_sinais": len(sig_n),
        "referencia_taxa_sinal": round(len(sig_n) / series, 4) if series else None,
        "referencia_confirmados_pct": nc,
        "referencia_confirmacao_acaso_pct": nb,
    }


def run(con: duckdb.DuckDBPyConnection | None = None) -> dict:
    con = con or duckdb.connect()
    g = C.GOLD.as_posix()
    max_ok = con.execute(f"SELECT semana_completa_ate FROM '{g}/meta.parquet'").fetchone()[0]
    sinais, avaliacao = [], []
    for cat in CATEGORIAS:
        X, s, (weeks, muns) = _panel(con, cat, max_ok)
        last = len(weeks) - 1
        for j, m in enumerate(muns):
            sig = cusum_detect(X[:, j], s, last)
            if sig:
                sinais.append(
                    (m, cat, sig.direcao, weeks[sig.inicio], last - sig.inicio + 1,
                     round(sig.razao, 3), sig.observado, round(sig.esperado, 1), round(sig.cusum_max, 2))
                )  # fmt: skip
        retro = retrospective(X, s, last)
        avaliacao.append({"tipo": "retrospectiva", "categoria": cat, **retro})
        if cat == "roubo":  # a simulação usa a forma estadual de um crime de alto volume
            for r in simulate(s):
                avaliacao.append({"tipo": "simulacao", "categoria": cat, **r})
    con.execute(
        "CREATE OR REPLACE TEMP TABLE mud (cd_ibge INTEGER, categoria VARCHAR, direcao VARCHAR, "
        "inicio DATE, semanas INTEGER, razao DOUBLE, observado DOUBLE, esperado DOUBLE, cusum_max DOUBLE)"
    )
    if sinais:
        con.executemany("INSERT INTO mud VALUES (?,?,?,?,?,?,?,?,?)", sinais)
    con.execute(
        f"COPY (SELECT *, DATE '{max_ok}' AS semana_referencia FROM mud) "
        f"TO '{g}/mudancas.parquet' (FORMAT parquet)"
    )
    cols = sorted({k for r in avaliacao for k in r})
    con.execute(
        "CREATE OR REPLACE TEMP TABLE ava ("
        + ", ".join(
            f"{c} {'VARCHAR' if c in ('tipo', 'categoria', 'cenario') else 'DOUBLE'}" for c in cols
        )
        + ")"
    )
    con.executemany(
        f"INSERT INTO ava VALUES ({','.join('?' * len(cols))})",
        [tuple(r.get(c) for c in cols) for r in avaliacao],
    )
    con.execute(f"COPY ava TO '{g}/mudancas_avaliacao.parquet' (FORMAT parquet)")
    return {"sinais": len(sinais), "avaliacao": avaliacao}
