"""Endpoints analíticos: tendência/sazonalidade, comparações e anomalias."""

from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from . import db
from .settings import K_MIN

router = APIRouter(prefix="/v1", tags=["analises"])


class MesPonto(BaseModel):
    mes: date
    n: int


class Sazonalidade(BaseModel):
    mes: int = Field(description="1 = janeiro ... 12 = dezembro")
    indice: float = Field(description="1,0 = média do ano; >1 = mês acima da média.")


class Tendencia(BaseModel):
    completo_ate: date
    serie: list[MesPonto]
    sazonalidade: list[Sazonalidade]
    variacao_12m_pct: float | None = Field(
        description="Últimos 12 meses completos vs. 12 anteriores."
    )
    inclinacao_pct_ano: float | None = Field(
        description="Inclinação linear dos últimos 24 meses completos, em % da média por ano."
    )
    suprimido: bool
    nota: str


class ComparacaoPeriodos(BaseModel):
    a: int | None
    b: int | None
    variacao_pct: float | None
    suprimido: bool


class Variacao(BaseModel):
    cd_ibge: int
    municipio: str
    a: int
    b: int
    variacao_pct: float


class RegiaoSerie(BaseModel):
    cd_ibge: int
    municipio: str
    populacao_2022: int | None
    ocorrencias: int | None
    taxa_100k: float | None
    serie_taxa_100k: list[tuple[date, float]]


class Anomalia(BaseModel):
    nivel: str
    id: str
    nome: str | None = Field(description="Nome do município (nível município) ou nulo.")
    categoria: str
    semana: date
    n: int
    esperado: float
    z: float
    razao: float


class AnomaliasResponse(BaseModel):
    semana_completa_ate: date
    metodo: str
    itens: list[Anomalia]


@db.ttl_cache
def completo_ate() -> date:
    return db.query("SELECT semana_completa_ate AS d FROM meta")[0]["d"] + timedelta(days=6)


def _where(categoria: str | None, cd_ibge: int | None) -> tuple[str, list]:
    where, params = "TRUE", []
    for col, val in (("categoria", categoria), ("cd_ibge", cd_ibge)):
        if val is not None:
            where += f" AND {col} = ?"
            params.append(val)
    return where, params


def _meses_completos(rows: list[dict], ate: date) -> list[dict]:
    """Mês só é completo se o último dia já passou do fim da última semana completa."""
    out = []
    for r in rows:
        m = r["mes"]
        nxt = date(m.year + (m.month == 12), m.month % 12 + 1, 1)
        if nxt - timedelta(days=1) <= ate:
            out.append(r)
    return out


def _slope_pct_per_year(ys: list[int]) -> float | None:
    n = len(ys)
    mean = sum(ys) / n if n else 0
    if n < 12 or mean == 0:
        return None
    xs = range(n)
    xm = (n - 1) / 2
    sxy = sum((x - xm) * (y - mean) for x, y in zip(xs, ys, strict=True))
    sxx = sum((x - xm) ** 2 for x in xs)
    return round(12 * (sxy / sxx) / mean * 100, 1)


@router.get("/tendencia", response_model=Tendencia)
def tendencia(categoria: str | None = None, cd_ibge: int | None = None) -> Tendencia:
    where, params = _where(categoria, cd_ibge)
    rows = db.query(
        f"SELECT mes, sum(n)::INTEGER AS n FROM mun_month WHERE {where} GROUP BY 1 ORDER BY 1",
        params,
    )
    ate = completo_ate()
    rows = _meses_completos(rows, ate)
    nota = (
        "Tendência por regressão linear simples; sazonalidade = média do índice mensal nos "
        "anos completos. Sem controle de feriados ou mudanças de registro."
    )
    if not rows or sum(r["n"] for r in rows) < K_MIN * 12:
        return Tendencia(
            completo_ate=ate, serie=[], sazonalidade=[], variacao_12m_pct=None,
            inclinacao_pct_ano=None, suprimido=True, nota=nota,
        )  # fmt: skip
    ys = [r["n"] for r in rows]
    var12 = None
    if len(ys) >= 24 and sum(ys[-24:-12]) > 0:
        var12 = round((sum(ys[-12:]) / sum(ys[-24:-12]) - 1) * 100, 1)
    by_year: dict[int, dict[int, int]] = {}
    for r in rows:
        by_year.setdefault(r["mes"].year, {})[r["mes"].month] = r["n"]
    idx: dict[int, list[float]] = {m: [] for m in range(1, 13)}
    for months in by_year.values():
        if len(months) == 12:
            avg = sum(months.values()) / 12
            for m, v in months.items():
                idx[m].append(v / avg)
    saz = [Sazonalidade(mes=m, indice=round(sum(v) / len(v), 3)) for m, v in idx.items() if v]
    return Tendencia(
        completo_ate=ate,
        serie=[MesPonto(**r) for r in rows],
        sazonalidade=saz,
        variacao_12m_pct=var12,
        inclinacao_pct_ano=_slope_pct_per_year(ys[-24:]),
        suprimido=False,
        nota=nota,
    )


def _periodo_sum(categoria, cd_ibge, ini: date, fim: date) -> int:
    where, params = _where(categoria, cd_ibge)
    r = db.query(
        f"SELECT coalesce(sum(n), 0)::INTEGER AS n FROM mun_month "
        f"WHERE {where} AND mes >= ? AND mes <= ?",
        [*params, ini.replace(day=1), fim],
    )
    return r[0]["n"]


@router.get("/comparacao/periodos", response_model=ComparacaoPeriodos)
def comparar_periodos(
    inicio_a: date,
    fim_a: date,
    inicio_b: date,
    fim_b: date,
    categoria: str | None = None,
    cd_ibge: int | None = None,
) -> ComparacaoPeriodos:
    if inicio_a > fim_a or inicio_b > fim_b:
        raise HTTPException(422, "inicio deve ser anterior a fim")
    a = _periodo_sum(categoria, cd_ibge, inicio_a, fim_a)
    b = _periodo_sum(categoria, cd_ibge, inicio_b, fim_b)
    if a < K_MIN or b < K_MIN:
        return ComparacaoPeriodos(a=None, b=None, variacao_pct=None, suprimido=True)
    return ComparacaoPeriodos(a=a, b=b, variacao_pct=round((b / a - 1) * 100, 1), suprimido=False)


@router.get("/comparacao/variacao-municipios", response_model=list[Variacao])
def maiores_variacoes(
    inicio_a: date,
    fim_a: date,
    inicio_b: date,
    fim_b: date,
    categoria: str | None = None,
    base_minima: int = Query(100, ge=K_MIN, description="Mínimo de ocorrências no período A."),
    sentido: str = Query("alta", pattern="^(alta|queda)$"),
    limit: int = Query(10, ge=1, le=50),
) -> list[Variacao]:
    cat = "AND categoria = ?" if categoria else ""
    extra = [categoria] if categoria else []
    order = "DESC" if sentido == "alta" else "ASC"
    rows = db.query(
        f"""
        WITH a AS (SELECT cd_ibge, sum(n) AS n FROM mun_month
                   WHERE mes >= ? AND mes <= ? {cat} GROUP BY 1),
             b AS (SELECT cd_ibge, sum(n) AS n FROM mun_month
                   WHERE mes >= ? AND mes <= ? {cat} GROUP BY 1)
        SELECT m.cd_ibge, m.municipio, a.n::INTEGER AS a, b.n::INTEGER AS b,
               round((b.n * 1.0 / a.n - 1) * 100, 1) AS variacao_pct
        FROM a JOIN b USING (cd_ibge) JOIN municipios m USING (cd_ibge)
        WHERE a.n >= ? AND b.n >= {K_MIN}
        ORDER BY variacao_pct {order} LIMIT ?""",
        [inicio_a.replace(day=1), fim_a, *extra, inicio_b.replace(day=1), fim_b, *extra,
         base_minima, limit],
    )  # fmt: skip
    return [Variacao(**r) for r in rows]


@router.get("/comparacao/regioes", response_model=list[RegiaoSerie])
def comparar_regioes(
    cd_ibge: list[int] = Query(..., min_length=1, max_length=6),
    categoria: str | None = None,
    inicio: date | None = None,
    fim: date | None = None,
) -> list[RegiaoSerie]:
    ate = completo_ate()
    fim = fim or ate
    inicio = (inicio or date(fim.year - 2, fim.month, 1)).replace(day=1)
    cat = "AND categoria = ?" if categoria else ""
    extra = [categoria] if categoria else []
    ids = ",".join("?" for _ in cd_ibge)
    muns = {
        m["cd_ibge"]: m
        for m in db.query(f"SELECT * FROM municipios WHERE cd_ibge IN ({ids})", cd_ibge)
    }
    out = []
    for c in cd_ibge:
        m = muns.get(c)
        if not m:
            raise HTTPException(404, f"município {c} não encontrado")
        rows = _meses_completos(
            db.query(
                f"SELECT mes, sum(n)::INTEGER AS n FROM mun_month WHERE cd_ibge = ? {cat} "
                "AND mes >= ? AND mes <= ? GROUP BY 1 ORDER BY 1",
                [c, *extra, inicio, fim],
            ),
            ate,
        )
        total = sum(r["n"] for r in rows)
        pop = m["populacao_2022"]
        ok = pop and total >= K_MIN
        out.append(
            RegiaoSerie(
                cd_ibge=c,
                municipio=m["municipio"],
                populacao_2022=pop,
                ocorrencias=total if total >= K_MIN else None,
                taxa_100k=round(total * 1e5 / pop, 1) if ok else None,
                serie_taxa_100k=[
                    (r["mes"], round(r["n"] * 1e5 / pop, 2)) for r in rows if ok and r["n"] >= K_MIN
                ],
            )
        )
    return out


@router.get("/anomalias", response_model=AnomaliasResponse)
def anomalias(
    nivel: str = Query("municipio", pattern="^(municipio|h3_7)$"),
    categoria: str | None = None,
    desde: date | None = Query(None, description="Semana inicial (padrão: últimas 8 semanas)."),
    limit: int = Query(20, ge=1, le=100),
) -> AnomaliasResponse:
    ate = db.query("SELECT semana_completa_ate AS d FROM meta")[0]["d"]
    desde = desde or ate - timedelta(weeks=7)
    cat = "AND a.categoria = ?" if categoria else ""
    params = [nivel, desde] + ([categoria] if categoria else []) + [limit]
    rows = db.query(
        f"""SELECT a.nivel, a.id, m.municipio AS nome, a.categoria, a.semana,
                   a.n::INTEGER AS n, a.esperado, a.z, a.razao
            FROM anomalias a
            LEFT JOIN municipios m ON a.nivel = 'municipio' AND a.id = CAST(m.cd_ibge AS VARCHAR)
            WHERE a.nivel = ? AND a.semana >= ? {cat}
            ORDER BY a.z DESC LIMIT ?""",
        params,
    )
    return AnomaliasResponse(
        semana_completa_ate=ate,
        metodo=(
            "Contagem semanal vs. mediana das 12 semanas anteriores; escala robusta (MAD) com piso "
            f"de ruído de Poisson; sinaliza z>=3, razão>=1,3 e n>=10 (k-mínimo {K_MIN}). "
            "Picos costumam refletir eventos de massa ou lotes de registro, não crime real."
        ),
        itens=[Anomalia(**r) for r in rows],
    )
