import csv
import io
import unicodedata
from datetime import date

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from . import db
from .analysis import completo_ate
from .analysis import router as analysis_router
from .investigacao import router as investigacao_router
from .previsao import router as previsao_router
from .protecao import agregado, arredondar_celula, janela_ancorada, publicar
from .qualidade import router as qualidade_router
from .radar import router as radar_router
from .schemas import (
    Categoria,
    Cell,
    HeatmapResponse,
    HourDowCell,
    Meta,
    MunicipioRef,
    MunicipioRow,
    Page,
    SeriesPoint,
)
from .settings import BRAND, CELL_ROUND, CORS_ORIGINS, K_MIN

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

app.include_router(analysis_router)
app.include_router(previsao_router)
app.include_router(radar_router)
app.include_router(qualidade_router)
app.include_router(investigacao_router)


def _ascii(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


@db.ttl_cache
def _dados_ate() -> date:
    """Fim da última semana com volume não residual (definido no pipeline, gold/meta)."""
    return db.query("SELECT dados_ate AS d FROM meta")[0]["d"]


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
    v = db.query("SELECT fonte_atualizada_em, processado_em FROM meta")[0]
    return Meta(
        marca=BRAND,
        dados_ate=_dados_ate(),
        completo_ate=completo_ate(),
        fonte_atualizada_em=v["fonte_atualizada_em"],
        processado_em=v["processado_em"],
        arredondamento_celulas=CELL_ROUND,
        k_min=K_MIN,
        categorias=list(CATEGORIAS),
        avisos=AVISOS,
    )


@app.get("/v1/categorias", response_model=list[Categoria], tags=["meta"])
def categorias() -> list[Categoria]:
    return [Categoria(id=k, nome=v) for k, v in CATEGORIAS.items()]


@db.ttl_cache
def _heatmap(inicio: date, fim: date, categoria: str | None, limit: int) -> tuple[int, int, list]:
    sql, params = agregado("cell_month", ["h3"], "mes >= ? AND mes <= ?", [inicio, fim], categoria)
    rows = db.query(f"SELECT h3, n::INTEGER AS n FROM ({sql})", params)
    kept = sorted(
        ({"h3": r["h3"], "n": arredondar_celula(r["n"])} for r in rows if r["n"] >= K_MIN),
        key=lambda r: -r["n"],
    )
    return len(rows), len(rows) - len(kept), kept[:limit]


@app.get("/v1/heatmap/h3", response_model=HeatmapResponse, tags=["mapa"])
def heatmap(
    categoria: str | None = Query(None, description="Categoria de crime (ver /v1/categorias)."),
    inicio: date | None = Query(
        None,
        description="Início (1º dia do mês); janela de 3, 6, 12 ou 24 meses até a data dos dados.",
    ),
    fim: date | None = Query(None, description="Se informado, deve ser igual à data dos dados."),
    limit: int = Query(30000, ge=1, le=60000),
) -> HeatmapResponse:
    _check_cat(categoria)
    inicio, fim = janela_ancorada(inicio, fim, _dados_ate())
    total, suprimidas, kept = _heatmap(inicio, fim, categoria, limit)
    return HeatmapResponse(
        inicio=inicio,
        fim=fim,
        categoria=categoria,
        k_min=K_MIN,
        arredondamento=CELL_ROUND,
        celulas_total=total,
        celulas_suprimidas=suprimidas,
        cells=[Cell(**r) for r in kept],
    )


def _mun_rows(categoria, inicio, fim, busca, ordenar, limit, offset) -> tuple[int, list[dict]]:
    """Consulta de municípios com taxa por 100 mil hab. e supressão k-mínimo."""
    _check_cat(categoria)
    inicio, fim = _periodo(inicio, fim)
    agg, params = agregado(
        "mun_month", ["cd_ibge"], "mes >= ? AND mes <= ?", [inicio, fim], categoria
    )
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
        LEFT JOIN ({agg}) a USING (cd_ibge)
        {name_filter}"""
    total = db.query(f"SELECT count(*) AS c FROM ({base})", params + name_params)[0]["c"]
    rows = db.query(
        f"SELECT * FROM ({base}) ORDER BY {order}, municipio LIMIT ? OFFSET ?",
        [*params, *name_params, limit, offset],
    )
    return total, rows


@app.get("/v1/municipios/lista", response_model=list[MunicipioRef], tags=["territorio"])
def municipios_lista() -> list[MunicipioRef]:
    """Todos os municípios (para busca/seleção). Não contém contagens."""
    return [
        MunicipioRef(**r)
        for r in db.query(
            "SELECT cd_ibge, municipio, populacao_2022 FROM municipios ORDER BY municipio"
        )
    ]


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
    total, rows = _mun_rows(
        categoria, inicio, fim, busca, ordenar, page_size, (page - 1) * page_size
    )
    return Page(
        items=[MunicipioRow(**r) for r in rows], total=total, page=page, page_size=page_size
    )


def _csv(header: list[str], rows: list[list], filename: str, comment: str) -> Response:
    """CSV UTF-8 com BOM (abre direto no Excel) e linhas de metadados iniciadas em '#'."""
    buf = io.StringIO()
    buf.write(f"# {comment}\n")
    buf.write(f"# Fonte: SSP-SP e IBGE. Dados agregados; valores < {K_MIN} suprimidos.\n")
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return Response(
        content="﻿" + buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/v1/export/municipios.csv", tags=["exportacao"])
def export_municipios(
    categoria: str | None = None, inicio: date | None = None, fim: date | None = None
) -> Response:
    inicio, fim = _periodo(inicio, fim)
    _, rows = _mun_rows(categoria, inicio, fim, None, "municipio", 1000, 0)
    return _csv(
        ["cd_ibge", "municipio", "populacao_2022", "ocorrencias", "taxa_100k", "suprimido"],
        [
            [r["cd_ibge"], r["municipio"], r["populacao_2022"], r["ocorrencias"],
             r["taxa_100k"], r["suprimido"]]
            for r in rows
        ],
        f"sinalbr_municipios_{categoria or 'todos'}_{inicio}_{fim}.csv",
        f"Ocorrências por município, {categoria or 'todos os crimes'}, {inicio} a {fim}",
    )  # fmt: skip


@app.get("/v1/export/celulas.csv", tags=["exportacao"])
def export_celulas(
    categoria: str | None = None, inicio: date | None = None, fim: date | None = None
) -> Response:
    _check_cat(categoria)
    inicio, fim = janela_ancorada(inicio, fim, _dados_ate())
    _, _, kept = _heatmap(inicio, fim, categoria, 60000)
    return _csv(
        ["h3_res8", "ocorrencias"],
        [[r["h3"], r["n"]] for r in kept],
        f"sinalbr_celulas_{categoria or 'todos'}_{inicio}_{fim}.csv",
        f"Ocorrências por hexágono H3 res. 8 (~0,7 km²), {categoria or 'todos'}, {inicio} a {fim}",
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
    if cd_ibge is not None:
        where += " AND cd_ibge = ?"
        params.append(cd_ibge)
    sql, params = agregado("mun_month", ["mes"], where, params, categoria)
    rows = db.query(f"SELECT mes, n::INTEGER AS n FROM ({sql}) ORDER BY 1", params)
    ate = _dados_ate()
    out = []
    for r in rows:
        # Série municipal: meses abaixo de k são suprimidos (nulo), nunca exibidos como zero.
        n = r["n"] if cd_ibge is None else publicar(r["n"])
        out.append(
            SeriesPoint(
                periodo=r["mes"],
                n=n,
                suprimido=n is None,
                parcial=(r["mes"].year, r["mes"].month) >= (ate.year, ate.month),
            )
        )
    return out


@app.get("/v1/hora-dia", response_model=list[HourDowCell], tags=["series"])
def hora_dia(categoria: str | None = None, cd_ibge: int | None = None) -> list[HourDowCell]:
    """Grade completa 7 x 24: n nulo = suprimido (< k); zero = nenhum registro com hora."""
    _check_cat(categoria)
    where, params = "TRUE", []
    if cd_ibge is not None:
        where += " AND cd_ibge = ?"
        params.append(cd_ibge)
    sql, params = agregado("mun_hour_dow", ["dow", "hora"], where, params, categoria)
    got = {
        (r["dow"], r["hora"]): r["n"] for r in db.query(f"SELECT dow, hora, n FROM ({sql})", params)
    }
    return [
        HourDowCell(dow=d, hora=h, n=publicar(int(got.get((d, h), 0))))
        for d in range(7)
        for h in range(24)
    ]
