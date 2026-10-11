import unicodedata
from datetime import date

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .schemas import (
    Categoria,
    Cell,
    HeatmapResponse,
    HourDowCell,
    Meta,
    MunicipioRow,
    Page,
    SeriesPoint,
)
from .settings import CORS_ORIGINS, K_MIN

CATEGORIAS = {
    "roubo": "Roubo",
    "furto": "Furto",
    "homicidio": "Homicídio e tentativa",
    "lesao_corporal": "Lesão corporal dolosa",
    "sexual": "Crimes sexuais",
    "drogas": "Drogas",
    "armas": "Porte de arma",
    "transito": "Ocorrências de trânsito",
}
AVISOS = [
    "Boletins de ocorrência refletem o registro, não o crime real: há subnotificação.",
    "Dados agregados e anonimizados; células com poucas ocorrências são suprimidas.",
    "Modelos preditivos podem reforçar vieses de policiamento; não use para decisões individuais.",
    "Os meses mais recentes são parciais por atraso de registro.",
]

app = FastAPI(
    title="SinalBR API",
    version="0.1.0",
    description="Estatísticas criminais agregadas e anonimizadas (SSP-SP). Sem dados pessoais.",
)
app.add_middleware(
    CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["GET"], allow_headers=["*"]
)


def _ascii(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


@db.ttl_cache
def _dados_ate() -> date:
    return db.query("SELECT max(semana) + 6 AS d FROM mun_week")[0]["d"]


def _periodo(inicio: date | None, fim: date | None) -> tuple[date, date]:
    fim = fim or _dados_ate()
    if inicio is None:
        inicio = date(fim.year - 1, fim.month, 1)
    if inicio > fim:
        raise HTTPException(422, "inicio deve ser anterior a fim")
    return inicio.replace(day=1), fim


def _check_cat(categoria: str | None) -> None:
    if categoria and categoria not in CATEGORIAS:
        raise HTTPException(422, f"categoria inválida; use uma de {sorted(CATEGORIAS)}")


@app.get("/v1/meta", response_model=Meta, tags=["meta"])
def meta() -> Meta:
    return Meta(
        marca="SinalBR",
        dados_ate=_dados_ate(),
        k_min=K_MIN,
        categorias=list(CATEGORIAS),
        avisos=AVISOS,
    )


@app.get("/v1/categorias", response_model=list[Categoria], tags=["meta"])
def categorias() -> list[Categoria]:
    return [Categoria(id=k, nome=v) for k, v in CATEGORIAS.items()]


@db.ttl_cache
def _heatmap(inicio: date, fim: date, categoria: str | None, limit: int) -> tuple[int, int, list]:
    where, params = "mes >= ? AND mes <= ?", [inicio, fim]
    if categoria:
        where += " AND categoria = ?"
        params.append(categoria)
    rows = db.query(
        f"SELECT h3, sum(n)::INTEGER AS n FROM cell_month WHERE {where} GROUP BY h3", params
    )
    kept = sorted((r for r in rows if r["n"] >= K_MIN), key=lambda r: -r["n"])
    return len(rows), len(rows) - len(kept), kept[:limit]


@app.get("/v1/heatmap/h3", response_model=HeatmapResponse, tags=["mapa"])
def heatmap(
    categoria: str | None = Query(None, description="Categoria de crime (ver /v1/categorias)."),
    inicio: date | None = Query(None, description="Início (arredondado ao mês)."),
    fim: date | None = None,
    limit: int = Query(30000, ge=1, le=60000),
) -> HeatmapResponse:
    _check_cat(categoria)
    inicio, fim = _periodo(inicio, fim)
    total, suprimidas, kept = _heatmap(inicio, fim, categoria, limit)
    return HeatmapResponse(
        inicio=inicio,
        fim=fim,
        categoria=categoria,
        k_min=K_MIN,
        celulas_total=total,
        celulas_suprimidas=suprimidas,
        cells=[Cell(**r) for r in kept],
    )


@app.get("/v1/municipios", response_model=Page[MunicipioRow], tags=["territorio"])
def municipios(
    categoria: str | None = None,
    inicio: date | None = None,
    fim: date | None = None,
    busca: str | None = Query(None, min_length=2, description="Filtro por nome."),
    ordenar: str = Query("taxa_100k", pattern="^(taxa_100k|ocorrencias|municipio)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Page[MunicipioRow]:
    _check_cat(categoria)
    inicio, fim = _periodo(inicio, fim)
    where, params = "mes >= ? AND mes <= ?", [inicio, fim]
    if categoria:
        where += " AND categoria = ?"
        params.append(categoria)
    name_filter, name_params = "", []
    if busca:
        name_filter = "WHERE strip_accents(lower(m.municipio)) LIKE ?"
        name_params = [f"%{_ascii(busca)}%"]
    order = {
        "taxa_100k": "taxa_100k DESC NULLS LAST",
        "ocorrencias": "ocorrencias DESC NULLS LAST",
        "municipio": "municipio",
    }[ordenar]
    base = f"""
        SELECT m.cd_ibge, m.municipio, m.populacao_2022,
               CASE WHEN coalesce(a.n, 0) >= {K_MIN} THEN a.n::INTEGER END AS ocorrencias,
               (coalesce(a.n, 0) < {K_MIN}) AS suprimido,
               CASE WHEN a.n >= {K_MIN} THEN round(a.n * 100000.0 / m.populacao_2022, 1) END
                 AS taxa_100k
        FROM municipios m
        LEFT JOIN (SELECT cd_ibge, sum(n) AS n FROM mun_month WHERE {where} GROUP BY 1) a
          USING (cd_ibge)
        {name_filter}"""
    total = db.query(f"SELECT count(*) AS c FROM ({base})", params + name_params)[0]["c"]
    rows = db.query(
        f"SELECT * FROM ({base}) ORDER BY {order}, municipio LIMIT ? OFFSET ?",
        [*params, *name_params, page_size, (page - 1) * page_size],
    )
    return Page(
        items=[MunicipioRow(**r) for r in rows], total=total, page=page, page_size=page_size
    )


@app.get("/v1/series", response_model=list[SeriesPoint], tags=["series"])
def series(
    categoria: str | None = None,
    cd_ibge: int | None = Query(None, description="Código IBGE do município (omitir = estado)."),
    inicio: date | None = None,
    fim: date | None = None,
) -> list[SeriesPoint]:
    _check_cat(categoria)
    fim = fim or _dados_ate()
    inicio = (inicio or date(2022, 1, 1)).replace(day=1)
    where, params = "mes >= ? AND mes <= ?", [inicio, fim]
    for col, val in (("categoria", categoria), ("cd_ibge", cd_ibge)):
        if val is not None:
            where += f" AND {col} = ?"
            params.append(val)
    rows = db.query(
        f"SELECT mes, sum(n)::INTEGER AS n FROM mun_month WHERE {where} GROUP BY 1 ORDER BY 1",
        params,
    )
    ate = _dados_ate()
    return [
        SeriesPoint(
            periodo=r["mes"],
            # Supressão: série municipal não revela meses com menos de k_min ocorrências.
            n=r["n"] if (r["n"] >= K_MIN or cd_ibge is None) else 0,
            parcial=(r["mes"].year, r["mes"].month) >= (ate.year, ate.month),
        )
        for r in rows
    ]


@app.get("/v1/hora-dia", response_model=list[HourDowCell], tags=["series"])
def hora_dia(categoria: str | None = None, cd_ibge: int | None = None) -> list[HourDowCell]:
    _check_cat(categoria)
    where, params = "TRUE", []
    for col, val in (("categoria", categoria), ("cd_ibge", cd_ibge)):
        if val is not None:
            where += f" AND {col} = ?"
            params.append(val)
    rows = db.query(
        f"SELECT dow, hora, sum(n)::INTEGER AS n FROM mun_hour_dow WHERE {where} GROUP BY 1, 2",
        params,
    )
    return [HourDowCell(**r) for r in rows if r["n"] >= K_MIN]
