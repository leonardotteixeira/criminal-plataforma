"""Detector de mudanças persistentes nas séries semanais por município x crime.

Pergunta respondida: "o município passou a registrar, de forma sustentada, mais (ou menos)
ocorrências do que seria esperado?". Não responde por que isso aconteceu.

Modelos de esperado (mu_t) comparados
-------------------------------------
- ``share`` (v1): mu_t = p * S_t. S_t = total estadual do crime na semana; p = participação do
  município nas 26 semanas de linha de base. Absorve sazonalidade estadual, feriados, atraso de
  registro e tendência estadual, mas assume que o município tem a sazonalidade do estado.
- ``sazonal`` (alternativa avaliada e NÃO adotada): mu_t = p * S_t * f_t. f_t = quanto a participação do município, nas mesmas
  semanas do ano anterior (janela de 5 semanas), se afastou da participação na linha de base
  equivalente do ano anterior. Encolhido para 1 conforme o volume: f = 1 + w (r - 1),
  w = n / (n + LAMBDA). Corrige eventos anuais próprios (ex.: festa em agosto).

Teste
-----
Resíduo z_t = (x_t - mu_t) / sqrt(phi mu_t); phi = superdispersão na linha de base (>= 1).
CUSUM bilateral (K, H) nas 12 semanas monitoradas; "persistente" exige >= 4 semanas desde o
início estimado, magnitude >= 20% e últimas 4 semanas na mesma direção (>= 10%).

p-valor: probabilidade, sob H0 (z_t i.i.d. N(0,1), sem mudança), de o máximo bilateral do CUSUM
nas 12 semanas ser >= ao observado. Tabela nula simulada uma vez (semente fixa). É aproximado:
contagens baixas não são normais e phi é estimado.

Controle de múltiplas comparações: Benjamini-Hochberg (q = FDR_Q) sobre os p-valores de todas
as séries elegíveis na mesma origem.

Referência simples: razão das últimas 8 semanas sobre a média da linha de base (|r-1| >= 25% e z
de Poisson >= 3), sem ajuste estadual nem sazonal.

Avaliação: ver ``evaluate_real`` e ``simulate``; resultados em gold/mudancas_comparacao.parquet e
docs/mudancas.md.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import duckdb
import numpy as np

from . import config as C

BASE_WEEKS = 26
MONITOR_WEEKS = 12
YEAR = 52
SEASON_HALF = 2  # janela de 5 semanas no ano anterior
LAMBDA = 20.0  # encolhimento do fator sazonal (registros)
F_CLIP = (0.33, 3.0)
K = 0.5
H = 5.0
MIN_LEVEL = 3.0  # média esperada mínima por semana na linha de base
MIN_WEEKS = 4
MIN_MAGNITUDE = 0.20
TAIL_WEEKS = 4
TAIL_MIN = 0.10
CONFIRM_WEEKS = 8
FDR_Q = 0.10
METODOS = ("share", "sazonal")
# Método e filtro usados em produção (radar). Decididos pela avaliação em docs/mudancas.md:
# o modelo sazonal NÃO superou o de participação nos dados reais (pior sob a verdade neutra T1
# em todas as faixas e anos; converge para o mesmo resultado com encolhimento forte), então
# fica só como alternativa avaliada. BH dá ganho pequeno e consistente.
METODO_PRODUCAO = "share"
USAR_FDR = True
METODO_VERSAO = f"{METODO_PRODUCAO}{'+bh' if USAR_FDR else ''}-K{K}-H{H}"
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


@dataclass(frozen=True)
class Sinal:
    direcao: str  # "alta" | "queda"
    inicio: int  # índice da semana de início estimada
    alarme: int  # índice da semana em que o CUSUM cruzou H
    razao: float  # observado / esperado desde o início
    observado: float
    esperado: float
    cusum_max: float
    p_valor: float = 1.0


@dataclass(frozen=True)
class Avaliacao:
    """Resultado de uma série numa origem (com ou sem sinal)."""

    sinal: Sinal | None
    smax: float  # máximo bilateral do CUSUM (para o p-valor)
    p_valor: float
    nivel: float  # média esperada por semana na linha de base


# ---------------------------------------------------------------- distribuição nula do CUSUM
def _null_table(n: int = 100_000, seed: int = 12345) -> np.ndarray:
    rng = np.random.default_rng(seed)
    z = rng.standard_normal((n, MONITOR_WEEKS))
    up = np.zeros(n)
    dn = np.zeros(n)
    mu = np.zeros(n)
    md = np.zeros(n)
    for i in range(MONITOR_WEEKS):
        up = np.maximum(0, up + z[:, i] - K)
        dn = np.maximum(0, dn - z[:, i] - K)
        mu = np.maximum(mu, up)
        md = np.maximum(md, dn)
    return np.sort(np.maximum(mu, md))


_NULL = _null_table()


def p_value(smax: float) -> float:
    """P(máximo bilateral do CUSUM >= smax | H0), com correção (1 + k) / (N + 1)."""
    k = len(_NULL) - np.searchsorted(_NULL, smax, side="left")
    return float((1 + k) / (len(_NULL) + 1))


def benjamini_hochberg(p: np.ndarray, q: float = FDR_Q) -> np.ndarray:
    """Máscara das hipóteses rejeitadas pelo procedimento de Benjamini-Hochberg."""
    p = np.asarray(p, dtype=float)
    m = len(p)
    if m == 0:
        return np.zeros(0, dtype=bool)
    order = np.argsort(p)
    ok = p[order] <= q * np.arange(1, m + 1) / m
    keep = np.zeros(m, dtype=bool)
    if ok.any():
        keep[order[: np.max(np.nonzero(ok)[0]) + 1]] = True
    return keep


# ---------------------------------------------------------------- esperado
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


def seasonal_factors(x: np.ndarray, s: np.ndarray, end: int) -> np.ndarray | None:
    """Fator sazonal municipal f_t para as semanas monitoradas, a partir do ano anterior."""
    m0 = end - MONITOR_WEEKS + 1
    b0 = m0 - BASE_WEEKS
    lb0, lm0 = b0 - YEAR, m0 - YEAR
    if lb0 - SEASON_HALF < 0:
        return None
    sb = s[lb0:lm0].sum()
    xb = x[lb0:lm0].sum()
    if sb <= 0 or xb <= 0:
        return np.ones(MONITOR_WEEKS)  # sem registro no ano anterior: sem ajuste
    p_ly = xb / sb
    f = np.ones(MONITOR_WEEKS)
    for i, t in enumerate(range(m0, end + 1)):
        lo, hi = t - YEAR - SEASON_HALF, t - YEAR + SEASON_HALF + 1
        n, st = x[lo:hi].sum(), s[lo:hi].sum()
        if st <= 0:
            continue
        r = (n / st) / p_ly
        w = n / (n + LAMBDA)
        f[i] = 1 + w * (r - 1)
    return np.clip(f, *F_CLIP)


def expected(x: np.ndarray, s: np.ndarray, end: int, metodo: str = "share"):
    """(mu nas semanas monitoradas, phi, m0, nível) ou None se a série não é elegível."""
    base = _baseline(x, s, end)
    if base is None:
        return None
    p, phi, m0, _ = base
    mu = p * s[m0 : end + 1]
    nivel = float(p * s[m0 - BASE_WEEKS : m0].mean())
    if metodo == "sazonal":
        f = seasonal_factors(x, s, end)
        if f is None:
            return None
        mu = mu * f
    elif metodo != "share":
        raise ValueError(metodo)
    return mu, phi, m0, nivel


# ---------------------------------------------------------------- teste
def _cusum(
    xm: np.ndarray, mu: np.ndarray, phi: float, m0: int, h: float
) -> tuple[Sinal | None, float]:
    z = (xm - mu) / np.sqrt(phi * np.maximum(mu, 1e-9))
    found: Sinal | None = None
    smax = 0.0
    for direcao, sign in (("alta", 1.0), ("queda", -1.0)):
        cs, last_zero, alarme, cmax = 0.0, -1, None, 0.0
        for i, zi in enumerate(z):
            cs = max(0.0, cs + sign * zi - K)
            cmax = max(cmax, cs)
            if cs == 0.0 and alarme is None:
                last_zero = i
            if cs > h and alarme is None:
                alarme = i
        smax = max(smax, cmax)
        if alarme is None or found is not None:
            continue
        ini = last_zero + 1
        obs, esp = float(xm[ini:].sum()), float(mu[ini:].sum())
        razao = obs / esp if esp > 0 else np.inf
        tail = xm[-TAIL_WEEKS:].sum() / max(mu[-TAIL_WEEKS:].sum(), 1e-9)
        dur = len(xm) - ini
        ok_mag = razao >= 1 + MIN_MAGNITUDE if sign > 0 else razao <= 1 - MIN_MAGNITUDE
        ok_tail = tail >= 1 + TAIL_MIN if sign > 0 else tail <= 1 - TAIL_MIN
        if dur >= MIN_WEEKS and ok_mag and ok_tail:
            found = Sinal(direcao, m0 + ini, m0 + alarme, razao, obs, esp, cmax)
    return found, smax


def assess(
    x: np.ndarray, s: np.ndarray, end: int, metodo: str = "share", h: float = H
) -> Avaliacao | None:
    e = expected(x, s, end, metodo)
    if e is None:
        return None
    mu, phi, m0, nivel = e
    sig, smax = _cusum(x[m0 : end + 1], mu, phi, m0, h)
    pv = p_value(smax)
    return Avaliacao(replace(sig, p_valor=pv) if sig else None, smax, pv, nivel)


def cusum_detect(
    x: np.ndarray, s: np.ndarray, end: int, metodo: str = "share", h: float = H
) -> Sinal | None:
    """Mudança persistente na janela monitorada que termina em `end` (inclusive)."""
    a = assess(x, s, end, metodo, h)
    return a.sinal if a else None


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


# ---------------------------------------------------------------- avaliação em dados reais
def _future_truth(x: np.ndarray, s: np.ndarray, end: int) -> tuple[float, float] | None:
    """Razões futuras (8 semanas após a origem) sob duas verdades de referência.

    T1 (participação): x_fut / (p * S_fut).
    T2 (participação com sazonalidade do ano anterior): x_fut / (p * S_fut * f_fut), onde f_fut
    vem das mesmas semanas do ano anterior. T2 penaliza alarmes causados por eventos anuais.
    """
    base = _baseline(x, s, end)
    if base is None or end + CONFIRM_WEEKS >= len(x):
        return None
    p, _, m0, _ = base
    fut = slice(end + 1, end + 1 + CONFIRM_WEEKS)
    t1 = x[fut].sum() / max(p * s[fut].sum(), 1e-9)
    # fator sazonal para as semanas futuras, com a mesma regra de seasonal_factors
    lb0, lm0 = m0 - BASE_WEEKS - YEAR, m0 - YEAR
    if lb0 - SEASON_HALF < 0:
        return None
    xb, sb = x[lb0:lm0].sum(), s[lb0:lm0].sum()
    f = np.ones(CONFIRM_WEEKS)
    if xb > 0 and sb > 0:
        p_ly = xb / sb
        for i, t in enumerate(range(end + 1, end + 1 + CONFIRM_WEEKS)):
            lo, hi = t - YEAR - SEASON_HALF, t - YEAR + SEASON_HALF + 1
            n, st = x[lo:hi].sum(), s[lo:hi].sum()
            if st > 0:
                f[i] = 1 + (n / (n + LAMBDA)) * ((n / st) / p_ly - 1)
    f = np.clip(f, *F_CLIP)
    t2 = x[fut].sum() / max((p * s[fut] * f).sum(), 1e-9)
    return float(t1), float(t2)


def _confirmed(direcao: str, r: float) -> bool:
    return r >= 1.1 if direcao == "alta" else r <= 0.9


def evaluate_real(X: np.ndarray, s: np.ndarray, weeks: list, cat: str, hs=(H,)) -> list[dict]:
    """Registros por (origem, série, método) para métricas comparáveis.

    Só entram origens em que TODOS os métodos podem ser avaliados (mesmo conjunto de séries),
    para que as taxas sejam comparáveis. Origens a cada 4 semanas.
    """
    first = YEAR + SEASON_HALF + BASE_WEEKS + MONITOR_WEEKS - 1
    last = len(weeks) - 1 - CONFIRM_WEEKS
    out = []
    for end in range(first, last + 1, 4):
        ano = weeks[end].year
        for j in range(X.shape[1]):
            x = X[:, j]
            truth = _future_truth(x, s, end)
            if truth is None:
                continue
            base = {
                "categoria": cat,
                "origem": end,
                "ano": ano,
                "serie": j,
                "t1": truth[0],
                "t2": truth[1],
            }
            avals = {}
            for m in METODOS:
                for h in hs:
                    a = assess(x, s, end, m, h)
                    if a is None:
                        break
                    avals[(m, h)] = a
            if len(avals) != len(METODOS) * len(hs):
                continue
            nivel = avals[(METODOS[0], hs[0])].nivel
            for (m, h), a in avals.items():
                out.append({**base, "metodo": m, "h": h, "nivel": nivel, "p": a.p_valor,
                            "direcao": a.sinal.direcao if a.sinal else None})  # fmt: skip
            nv = naive_detect(x, end)
            out.append(
                {
                    **base,
                    "metodo": "referencia",
                    "h": None,
                    "nivel": nivel,
                    "p": None,
                    "direcao": nv,
                }
            )
    return out


def _bh_por_origem(rows: list[dict]) -> None:
    """Marca 'bh' = sinal que sobrevive ao BH aplicado entre todas as séries da origem."""
    grupos: dict[tuple, list[dict]] = {}
    for r in rows:
        if r["p"] is not None:
            grupos.setdefault((r["categoria"], r["origem"], r["metodo"], r["h"]), []).append(r)
    for g in grupos.values():
        keep = benjamini_hochberg(np.array([r["p"] for r in g]))
        for r, k in zip(g, keep, strict=True):
            r["bh"] = bool(k and r["direcao"])


def summarize(rows: list[dict], recorte: str, chave) -> list[dict]:
    """Métricas por método (e recorte) sob as verdades T1 e T2, com a taxa do acaso."""
    out = []
    grupos: dict[tuple, list[dict]] = {}
    for r in rows:
        variantes = [(r["metodo"], r["h"], False)]
        if r.get("bh") is not None and r["metodo"] != "referencia":
            variantes.append((r["metodo"] + "+bh", r["h"], True))
        for m, h, is_bh in variantes:
            grupos.setdefault((chave(r), m, h, is_bh), []).append(r)
    for (k, m, h, is_bh), g in sorted(grupos.items(), key=lambda t: str(t[0])):
        sinais = [r for r in g if (r.get("bh") if is_bh else r["direcao"])]
        n = len(g)
        rec = {"recorte_tipo": recorte, "recorte": str(k), "metodo": m, "h": h, "series": n,
               "sinais": len(sinais), "taxa_sinal": round(len(sinais) / n, 4) if n else None}  # fmt: skip
        for t in ("t1", "t2"):
            if not sinais:
                rec[f"conf_{t}"] = rec[f"acaso_{t}"] = rec[f"lift_{t}"] = None
                continue
            fut = np.array([r[t] for r in g])
            up, dn = float(np.mean(fut >= 1.1)), float(np.mean(fut <= 0.9))
            conf = float(np.mean([_confirmed(r["direcao"], r[t]) for r in sinais]))
            acaso = float(np.mean([up if r["direcao"] == "alta" else dn for r in sinais]))
            rec[f"conf_{t}"] = round(100 * conf, 1)
            rec[f"acaso_{t}"] = round(100 * acaso, 1)
            rec[f"lift_{t}"] = round(conf / acaso, 2) if acaso > 0 else None
        out.append(rec)
    return out


def stability(rows: list[dict]) -> list[dict]:
    """Estabilidade temporal: fração dos sinais numa origem que reaparecem (mesma direção) 4
    semanas depois, quando a série continua avaliável."""
    idx = {(r["categoria"], r["serie"], r["metodo"], r["h"], r["origem"]): r for r in rows}
    agg: dict[str, list[bool]] = {}
    for r in rows:
        if not r["direcao"]:
            continue
        nxt = idx.get((r["categoria"], r["serie"], r["metodo"], r["h"], r["origem"] + 4))
        if nxt is None:
            continue
        agg.setdefault(f"{r['metodo']}|{r['h']}", []).append(nxt["direcao"] == r["direcao"])
    return [
        {"metodo": k.split("|")[0], "h": None if k.split("|")[1] == "None" else float(k.split("|")[1]),
         "sinais_com_seguinte": len(v), "reaparecem_pct": round(100 * float(np.mean(v)), 1)}
        for k, v in sorted(agg.items())
    ]  # fmt: skip


def faixa(nivel: float) -> str:
    return "3-10/sem" if nivel < 10 else "10-30/sem" if nivel < 30 else ">=30/sem"


# ---------------------------------------------------------------- simulação
def _nb(rng, mean: np.ndarray, phi: float) -> np.ndarray:
    if phi <= 1:
        return rng.poisson(mean).astype(float)
    return rng.poisson(rng.gamma(mean / (phi - 1), phi - 1)).astype(float)


def simulate(
    s_real: np.ndarray,
    month_of_week: np.ndarray,
    padroes: np.ndarray,
    n_sims: int = 300,
    seed: int = 0,
) -> list[dict]:
    """Falso alarme, poder e atraso com a forma real da série estadual.

    `padroes`: índices sazonais mensais reais da participação de municípios (linhas de 12);
    no cenário "com sazonalidade municipal", cada série simulada recebe um padrão sorteado.
    """
    rng = np.random.default_rng(seed)
    L = YEAR + SEASON_HALF + BASE_WEEKS + MONITOR_WEEKS
    starts = np.arange(0, len(s_real) - L)
    change_at = L - MONITOR_WEEKS + 3  # 4ª semana monitorada
    out = []
    for saz in (False, True):
        for lam in (3.0, 10.0, 30.0):
            for step, nome in (
                (1.0, "sem_mudanca"),
                (1.3, "alta_30"),
                (1.5, "alta_50"),
                (0.7, "queda_30"),
            ):
                hits = {m: 0 for m in (*METODOS, "referencia")}
                delays = {m: [] for m in METODOS}
                want = None if step == 1.0 else ("alta" if step > 1 else "queda")
                for _ in range(n_sims):
                    o = int(rng.choice(starts))
                    s = s_real[o : o + L].astype(float)
                    f = (
                        padroes[rng.integers(len(padroes))][month_of_week[o : o + L]]
                        if saz
                        else 1.0
                    )
                    mean = lam * s / s[:BASE_WEEKS].mean() * f
                    mean = mean * np.where(np.arange(L) >= change_at, step, 1.0)
                    x = _nb(rng, mean, 1.5)
                    for m in METODOS:
                        sig = cusum_detect(x, s, L - 1, m)
                        if sig and (want is None or sig.direcao == want):
                            hits[m] += 1
                            if want:
                                delays[m].append(sig.alarme - change_at)
                    nv = naive_detect(x, L - 1)
                    if nv and (want is None or nv == want):
                        hits["referencia"] += 1
                for m, h in hits.items():
                    out.append(
                        {"sazonalidade_municipal": saz, "nivel_semanal": lam, "cenario": nome, "metodo": m,
                         "taxa_sinal": round(h / n_sims, 4),
                         "atraso_medio_semanas": round(float(np.mean(delays[m])), 2) if delays.get(m) else None}
                    )  # fmt: skip
    return out


def simulate_fdr(
    s_real: np.ndarray,
    month_of_week: np.ndarray,
    padroes: np.ndarray,
    batches: int = 20,
    seed: int = 1,
) -> list[dict]:
    """Lotes mistos (10% com alta de 50%, 90% sem mudança, com sazonalidade municipal):
    proporção de falsas descobertas e poder, com e sem Benjamini-Hochberg."""
    rng = np.random.default_rng(seed)
    L = YEAR + SEASON_HALF + BASE_WEEKS + MONITOR_WEEKS
    starts = np.arange(0, len(s_real) - L)
    change_at = L - MONITOR_WEEKS + 3
    out = []
    for lam in (10.0, 30.0):
        acc = {(m, bh): {"fdp": [], "poder": []} for m in METODOS for bh in (False, True)}
        for _ in range(batches):
            o = int(rng.choice(starts))
            s = s_real[o : o + L].astype(float)
            n = 300
            real = rng.random(n) < 0.10
            res = {m: [] for m in METODOS}
            for i in range(n):
                f = padroes[rng.integers(len(padroes))][month_of_week[o : o + L]]
                mean = lam * s / s[:BASE_WEEKS].mean() * f
                if real[i]:
                    mean = mean * np.where(np.arange(L) >= change_at, 1.5, 1.0)
                x = _nb(rng, mean, 1.5)
                for m in METODOS:
                    res[m].append(assess(x, s, L - 1, m))
            for m in METODOS:
                a = res[m]
                sig = np.array([bool(v and v.sinal and v.sinal.direcao == "alta") for v in a])
                anysig = np.array([bool(v and v.sinal) for v in a])
                pv = np.array([v.p_valor if v else 1.0 for v in a])
                for bh in (False, True):
                    flag = anysig & benjamini_hochberg(pv) if bh else anysig
                    tp = (flag & sig & real).sum()
                    fp = (flag & ~real).sum()
                    acc[(m, bh)]["fdp"].append(fp / max(flag.sum(), 1))
                    acc[(m, bh)]["poder"].append(tp / max(real.sum(), 1))
        for (m, bh), v in acc.items():
            out.append(
                {"nivel_semanal": lam, "metodo": m + ("+bh" if bh else ""),
                 "fdp_media_pct": round(100 * float(np.mean(v["fdp"])), 1),
                 "poder_pct": round(100 * float(np.mean(v["poder"])), 1)}
            )  # fmt: skip
    return out


# ---------------------------------------------------------------- compatibilidade (v1)
def retrospective(X: np.ndarray, s: np.ndarray, last: int, metodo: str = "share") -> dict:
    """Resumo retrospectivo do método indicado (verdade T1), com a referência simples.

    Mantido para compatibilidade com a avaliação v1 (gold/mudancas_avaliacao).
    """
    first = BASE_WEEKS + MONITOR_WEEKS - 1
    sig_c, sig_n, fut_c, fut_n = [], [], [], []
    series = 0
    for end in range(first, last - CONFIRM_WEEKS + 1, 4):
        fut = slice(end + 1, end + 1 + CONFIRM_WEEKS)
        for j in range(X.shape[1]):
            x = X[:, j]
            e = expected(x, s, end, metodo)
            if e is None:
                continue
            series += 1
            base = _baseline(x, s, end)
            p, _, m0, _ = base
            r_c = x[fut].sum() / max(p * s[fut].sum(), 1e-9)
            r_n = x[fut].sum() / max(CONFIRM_WEEKS * x[m0 - BASE_WEEKS : m0].mean(), 1e-9)
            fut_c.append(r_c)
            fut_n.append(r_n)
            sig = cusum_detect(x, s, end, metodo)
            if sig:
                sig_c.append((sig.direcao, _confirmed(sig.direcao, r_c)))
            nv = naive_detect(x, end)
            if nv:
                sig_n.append((nv, _confirmed(nv, r_n)))

    def resumo(sigs, futs):
        if not sigs:
            return None, None
        f = np.asarray(futs)
        up, dn = float(np.mean(f >= 1.1)), float(np.mean(f <= 0.9))
        conf = 100 * np.mean([ok for _, ok in sigs])
        base = 100 * np.mean([up if d == "alta" else dn for d, _ in sigs])
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


def _padroes_sazonais(con: duckdb.DuckDBPyConnection) -> np.ndarray:
    """Índices mensais reais da participação municipal (séries com >= 40 registros/mês)."""
    g = C.GOLD.as_posix()
    rows = con.execute(
        f"""WITH m AS (SELECT cd_ibge, categoria, mes, n FROM '{g}/mun_month.parquet'
                       WHERE mes < date_trunc('year', (SELECT max(mes) FROM '{g}/mun_month.parquet'))),
            s AS (SELECT categoria, mes, sum(n) AS st FROM m GROUP BY ALL),
            sh AS (SELECT m.cd_ibge, m.categoria, month(m.mes) AS mm, sum(m.n) / sum(s.st) AS part
                   FROM m JOIN s USING (categoria, mes) GROUP BY ALL),
            v AS (SELECT cd_ibge, categoria FROM m GROUP BY ALL HAVING count(DISTINCT year(mes)) >= 2
                  AND sum(n) / count(DISTINCT mes) >= 40),
            idx AS (SELECT cd_ibge, categoria, mm,
                           part / avg(part) OVER (PARTITION BY cd_ibge, categoria) AS i
                    FROM sh JOIN v USING (cd_ibge, categoria))
            SELECT cd_ibge, categoria, list(i ORDER BY mm) FROM idx GROUP BY ALL"""
    ).fetchall()
    pads = [r[2] for r in rows if len(r[2]) == 12]
    # coluna 0 vazia para indexar diretamente pelo mês (1..12)
    return np.array([[1.0, *p] for p in pads]) if pads else np.ones((1, 13))


def detect_origin(X: np.ndarray, s: np.ndarray, end: int) -> list[tuple[int, Avaliacao, bool]]:
    """Avalia todas as séries elegíveis numa origem com o método de produção.

    Retorna (coluna, avaliação, passa_no_BH) para cada série ELEGÍVEL (com ou sem sinal); séries
    fora da lista não puderam ser avaliadas (volume ou histórico insuficiente).
    """
    aval = [(j, assess(X[:, j], s, end, METODO_PRODUCAO)) for j in range(X.shape[1])]
    aval = [(j, a) for j, a in aval if a is not None]
    if not aval:
        return []
    keep = benjamini_hochberg(np.array([a.p_valor for _, a in aval]))
    ok = keep if USAR_FDR else np.ones(len(aval), dtype=bool)
    return [(j, a, bool(k)) for (j, a), k in zip(aval, ok, strict=True)]


def run(con: duckdb.DuckDBPyConnection | None = None, avaliar: bool = True) -> dict:
    con = con or duckdb.connect()
    g = C.GOLD.as_posix()
    max_ok = con.execute(f"SELECT semana_completa_ate FROM '{g}/meta.parquet'").fetchone()[0]
    sinais, avaliacao, linhas = [], [], []
    s_roubo = weeks_roubo = None
    for cat in CATEGORIAS:
        X, s, (weeks, muns) = _panel(con, cat, max_ok)
        last = len(weeks) - 1
        for j, a, k in detect_origin(X, s, last):
            if a.sinal:
                sig = a.sinal
                sinais.append(
                    (muns[j], cat, sig.direcao, weeks[sig.inicio], last - sig.inicio + 1,
                     round(sig.razao, 3), sig.observado, round(sig.esperado, 1),
                     round(sig.cusum_max, 2), a.p_valor, bool(k), METODO_VERSAO)
                )  # fmt: skip
        if avaliar:
            retro = retrospective(X, s, last, METODO_PRODUCAO)
            avaliacao.append({"tipo": "retrospectiva", "categoria": cat, **retro})
            rows = evaluate_real(X, s, weeks, cat, hs=(4.0, H, 6.0))
            _bh_por_origem(rows)
            linhas += rows
        if cat == "roubo":
            s_roubo, weeks_roubo = s, weeks
    con.execute(
        "CREATE OR REPLACE TEMP TABLE mud (cd_ibge INTEGER, categoria VARCHAR, direcao VARCHAR, "
        "inicio DATE, semanas INTEGER, razao DOUBLE, observado DOUBLE, esperado DOUBLE, "
        "cusum_max DOUBLE, p_valor DOUBLE, fdr_ok BOOLEAN, metodo VARCHAR)"
    )
    if sinais:
        con.executemany("INSERT INTO mud VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", sinais)
    con.execute(
        f"COPY (SELECT *, DATE '{max_ok}' AS semana_referencia FROM mud) "
        f"TO '{g}/mudancas.parquet' (FORMAT parquet)"
    )
    if not avaliar:
        return {"sinais": len(sinais)}

    padroes = _padroes_sazonais(con)
    month_of_week = np.array([w.month for w in weeks_roubo])
    sim = simulate(s_roubo, month_of_week, padroes)
    for r in sim:
        if r["metodo"] == METODO_PRODUCAO and not r["sazonalidade_municipal"]:
            avaliacao.append(
                {"tipo": "simulacao", "categoria": "roubo", "nivel_semanal": r["nivel_semanal"],
                 "cenario": r["cenario"], "cusum_taxa_sinal": r["taxa_sinal"],
                 "referencia_taxa_sinal": next(
                     x["taxa_sinal"] for x in sim if x["metodo"] == "referencia" and x["cenario"] == r["cenario"]
                     and x["nivel_semanal"] == r["nivel_semanal"] and not x["sazonalidade_municipal"]),
                 "cusum_atraso_medio_semanas": r["atraso_medio_semanas"]}
            )  # fmt: skip
    _write(con, avaliacao, f"{g}/mudancas_avaliacao.parquet")

    h5 = [r for r in linhas if r["h"] in (H, None)]
    comp = summarize(h5, "geral", lambda r: "todas")
    comp += summarize(h5, "categoria", lambda r: r["categoria"])
    comp += summarize(h5, "faixa", lambda r: faixa(r["nivel"]))
    comp += summarize(h5, "ano", lambda r: r["ano"])
    comp += summarize(
        [r for r in linhas if r["metodo"] != "referencia"],
        "sensibilidade_h",
        lambda r: f"H={r['h']}",
    )
    _write(con, comp, f"{g}/mudancas_comparacao.parquet")
    _write(con, sim, f"{g}/mudancas_simulacao.parquet")
    fdr = simulate_fdr(s_roubo, month_of_week, padroes)
    _write(con, fdr, f"{g}/mudancas_fdr.parquet")
    estab = stability(h5)
    _write(con, estab, f"{g}/mudancas_estabilidade.parquet")
    return {
        "sinais": len(sinais),
        "comparacao": comp,
        "simulacao": sim,
        "fdr": fdr,
        "estabilidade": estab,
    }


def _write(con: duckdb.DuckDBPyConnection, rows: list[dict], path: str) -> None:
    """Grava uma lista de dicts como Parquet (tipos inferidos: texto, booleano ou número)."""
    cols = list(dict.fromkeys(k for r in rows for k in r))

    def tipo(c: str) -> str:
        vals = [r.get(c) for r in rows if r.get(c) is not None]
        if all(isinstance(v, bool) for v in vals) and vals:
            return "BOOLEAN"
        if all(isinstance(v, (int, float, np.integer, np.floating)) for v in vals):
            return "DOUBLE"
        return "VARCHAR"

    tipos = {c: tipo(c) for c in cols}
    con.execute(
        "CREATE OR REPLACE TEMP TABLE _w (" + ", ".join(f'"{c}" {tipos[c]}' for c in cols) + ")"
    )
    conv = lambda c, v: None if v is None else (str(v) if tipos[c] == "VARCHAR" else v)  # noqa: E731
    con.executemany(
        f"INSERT INTO _w VALUES ({','.join('?' * len(cols))})",
        [tuple(conv(c, r.get(c)) for c in cols) for r in rows],
    )
    con.execute(f"COPY _w TO '{path}' (FORMAT parquet)")
