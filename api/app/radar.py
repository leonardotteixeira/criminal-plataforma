"""Radar territorial: observações estatísticas que merecem investigação, com critérios explícitos.

Regras determinísticas e auditáveis (sem modelo de linguagem). Cada item informa o tipo, o
período, a região, as métricas e o critério que o fez aparecer. Nenhum item atribui causa.

Tipos
- mudanca_persistente: CUSUM sobre o modelo de participação no total estadual (gold/mudancas),
  só para categorias cuja avaliação retrospectiva sustenta o sinal.
- variacao: últimos 12 meses completos vs. 12 anteriores, comparada à variação do estado.
- anomalia: picos semanais (gold/anomalias) nas últimas 4 semanas completas, com recorrência.
- dados: semanas recentes incompletas e baixa cobertura do mapa para a categoria.
"""

import math
from datetime import date, timedelta

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from . import db
from .analysis import completo_ate, shift_months, ultimo_mes_completo
from .settings import K_MIN

router = APIRouter(prefix="/v1", tags=["radar"])

NOMES = {
    "roubo": "Roubo",
    "furto": "Furto",
    "homicidio": "Homicídio e tentativa",
    "lesao_corporal": "Lesão corporal dolosa",
    "sexual": "Crimes sexuais",
    "drogas": "Drogas",
    "armas": "Porte de arma",
    "transito": "Ocorrências de trânsito",
}
CATS = "^(" + "|".join(NOMES) + ")$"

# Critérios (expostos na resposta para auditoria)
VAR_BASE_MIN = 200
VAR_REL_MIN = 0.25
VAR_Z_MIN = 4.0
ANOM_SEMANAS = 4
ANOM_RECORRENTE = 3
MUD_MIN_SINAIS = 50
MUD_LIFT_MIN = 1.5
MONITOR_WEEKS = 12  # igual a data/src/sinalbr_data/changes.py
COBERTURA_MAPA_MIN = 60.0
CRITERIOS = {
    "mudanca_persistente": (
        "CUSUM bilateral (K=0,5, H=5) sobre resíduos do modelo de participação no total "
        "estadual; ≥ 4 semanas desde o início, magnitude ≥ 20% e últimas 4 semanas na mesma "
        f"direção. Só para categorias com ≥ {MUD_MIN_SINAIS} sinais históricos avaliados e "
        f"confirmação fora da amostra ≥ {MUD_LIFT_MIN}× a taxa do acaso."
    ),
    "variacao": (
        f"12 meses completos vs. 12 anteriores, com ≥ {VAR_BASE_MIN} registros no período "
        f"anterior; variação do município difere da do estado em ≥ {int(VAR_REL_MIN * 100)}% e "
        f"|z| ≥ {VAR_Z_MIN:g} (aproximação de Poisson; triagem, não teste formal)."
    ),
    "anomalia": (
        f"Pico semanal (z ≥ 3 vs. mediana de 12 semanas, n ≥ 10) nas últimas {ANOM_SEMANAS} "
        f"semanas completas; 'recorrente' se sinalizado em ≥ {ANOM_RECORRENTE} das últimas 8."
    ),
    "dados": (
        "Semanas recentes com volume abaixo de 85% da mediana das 8 anteriores; cobertura do "
        f"mapa abaixo de {COBERTURA_MAPA_MIN:g}% dos registros da categoria."
    ),
}


class RadarItem(BaseModel):
    tipo: str = Field(description="mudanca_persistente | variacao | anomalia | dados")
    categoria: str | None
    categoria_nome: str | None
    cd_ibge: int | None
    municipio: str | None
    periodo_inicio: date
    periodo_fim: date
    titulo: str
    explicacao: str
    direcao: str | None = Field(None, description="alta | queda (sem juízo de valor)")
    metricas: dict[str, float | int | None]
    forca: float = Field(description="Usada só para ordenar itens do mesmo tipo.")


class RadarResponse(BaseModel):
    referencia: date = Field(description="Fim da última semana completa.")
    criterios: dict[str, str]
    contagem: dict[str, int]
    itens: list[RadarItem]
    aviso: str


class Mudanca(BaseModel):
    cd_ibge: int
    municipio: str
    categoria: str
    direcao: str
    inicio: date
    semanas: int
    razao: float
    observado: int
    esperado: float
    confiavel: bool = Field(description="A avaliação retrospectiva da categoria sustenta o sinal.")


class AvaliacaoCategoria(BaseModel):
    categoria: str
    series_avaliadas: int
    sinais: int
    confirmados_pct: float | None
    confirmacao_acaso_pct: float | None
    referencia_confirmados_pct: float | None
    referencia_confirmacao_acaso_pct: float | None
    confiavel: bool


class Simulacao(BaseModel):
    nivel_semanal: float
    cenario: str
    cusum_taxa_sinal: float
    referencia_taxa_sinal: float
    cusum_atraso_medio_semanas: float | None


class MudancasResponse(BaseModel):
    referencia: date
    metodo: str
    itens: list[Mudanca]
    avaliacao: list[AvaliacaoCategoria]
    simulacao: list[Simulacao]


def _fmt(d: date) -> str:
    return d.strftime("%d/%m/%Y")


@db.ttl_cache
def avaliacao_por_categoria() -> dict[str, dict]:
    db.require("mudancas_avaliacao")
    rows = db.query(
        "SELECT categoria, series_avaliadas::DOUBLE AS series_avaliadas, "
        "cusum_sinais::DOUBLE AS cusum_sinais, "
        "cusum_confirmados_pct::DOUBLE AS cusum_confirmados_pct, "
        "cusum_confirmacao_acaso_pct::DOUBLE AS cusum_confirmacao_acaso_pct, "
        "referencia_confirmados_pct::DOUBLE AS referencia_confirmados_pct, "
        "referencia_confirmacao_acaso_pct::DOUBLE AS referencia_confirmacao_acaso_pct "
        "FROM mudancas_avaliacao WHERE tipo = 'retrospectiva'"
    )
    out = {}
    for r in rows:
        conf, acaso = r["cusum_confirmados_pct"], r["cusum_confirmacao_acaso_pct"]
        ok = bool(
            (r["cusum_sinais"] or 0) >= MUD_MIN_SINAIS
            and conf is not None
            and acaso
            and conf >= MUD_LIFT_MIN * acaso
        )
        out[r["categoria"]] = {**r, "confiavel": ok}
    return out


def _filtros(categoria, cd_ibge, alias="") -> tuple[str, list]:
    w, p = "", []
    if categoria:
        w += f" AND {alias}categoria = ?"
        p.append(categoria)
    if cd_ibge is not None:
        w += f" AND {alias}cd_ibge = ?"
        p.append(cd_ibge)
    return w, p


def _mudancas(categoria, cd_ibge, ref: date) -> list[RadarItem]:
    aval = avaliacao_por_categoria()
    w, p = _filtros(categoria, cd_ibge, "d.")
    rows = db.query(
        f"""SELECT d.*, m.municipio FROM mudancas d JOIN municipios m USING (cd_ibge)
            WHERE TRUE {w} ORDER BY d.cusum_max DESC""",
        p,
    )
    itens = []
    for r in rows:
        a = aval.get(r["categoria"])
        if not a or not a["confiavel"]:
            continue
        alta = r["direcao"] == "alta"
        pct = (r["razao"] - 1) * 100
        # Início na 1ª semana monitorada = a mudança pode ter começado antes da janela.
        desde = "desde pelo menos" if r["semanas"] >= MONITOR_WEEKS else "desde"
        itens.append(
            RadarItem(
                tipo="mudanca_persistente",
                categoria=r["categoria"],
                categoria_nome=NOMES.get(r["categoria"]),
                cd_ibge=r["cd_ibge"],
                municipio=r["municipio"],
                periodo_inicio=r["inicio"],
                periodo_fim=ref,
                direcao=r["direcao"],
                titulo=(
                    f"{NOMES[r['categoria']]}: registros {'acima' if alta else 'abaixo'} do "
                    f"padrão estadual {desde} {_fmt(r['inicio'])}"
                ),
                explicacao=(
                    f"Nas {r['semanas']} semanas {desde} {_fmt(r['inicio'])}, {int(r['observado'])} "
                    f"registros contra ~{r['esperado']:.0f} esperados se o município seguisse o "
                    f"estado ({pct:+.0f}%). Historicamente, {a['cusum_confirmados_pct']:.0f}% "
                    f"dos sinais desta categoria se mantiveram nas 8 semanas seguintes (por acaso: "
                    f"{a['cusum_confirmacao_acaso_pct']:.0f}%)."
                ),
                metricas={
                    "observado": int(r["observado"]),
                    "esperado": round(r["esperado"], 1),
                    "razao": round(r["razao"], 3),
                    "semanas": r["semanas"],
                },
                forca=round(r["cusum_max"], 2),
            )
        )
    return itens


def _variacoes(categoria, cd_ibge, ref_mes: date) -> list[RadarItem]:
    b_ini, b_fim = shift_months(ref_mes, -11), ref_mes
    a_ini, a_fim = shift_months(ref_mes, -23), shift_months(ref_mes, -12)
    wc, pc = ("AND categoria = ?", [categoria]) if categoria else ("", [])
    rows = db.query(
        f"""WITH m AS (
              SELECT cd_ibge, categoria,
                     sum(n) FILTER (WHERE mes BETWEEN ? AND ?) AS a,
                     sum(n) FILTER (WHERE mes BETWEEN ? AND ?) AS b
              FROM mun_month WHERE mes BETWEEN ? AND ? {wc} GROUP BY ALL),
            s AS (SELECT categoria, sum(a) AS sa, sum(b) AS sb FROM m GROUP BY 1)
            SELECT m.*, s.sa, s.sb, mu.municipio FROM m JOIN s USING (categoria)
            JOIN municipios mu USING (cd_ibge)
            WHERE m.a >= ? AND m.b >= ?""",
        [a_ini, a_fim, b_ini, b_fim, a_ini, b_fim, *pc, VAR_BASE_MIN, K_MIN],
    )
    itens = []
    for r in rows:
        if cd_ibge is not None and r["cd_ibge"] != cd_ibge:
            continue
        rm, rs = r["b"] / r["a"], r["sb"] / r["sa"]
        rel = rm / rs
        z = math.log(rel) / math.sqrt(1 / r["a"] + 1 / r["b"])
        if abs(rel - 1) < VAR_REL_MIN or abs(z) < VAR_Z_MIN:
            continue
        alta = rel > 1
        itens.append(
            RadarItem(
                tipo="variacao",
                categoria=r["categoria"],
                categoria_nome=NOMES.get(r["categoria"]),
                cd_ibge=r["cd_ibge"],
                municipio=r["municipio"],
                periodo_inicio=b_ini,
                periodo_fim=shift_months(b_fim, 1) - timedelta(days=1),
                direcao="alta" if alta else "queda",
                titulo=(
                    f"{NOMES[r['categoria']]}: variação anual "
                    f"{'acima' if alta else 'abaixo'} da do estado"
                ),
                explicacao=(
                    f"12 meses até {b_fim.strftime('%m/%Y')}: {int(r['b'])} registros vs. "
                    f"{int(r['a'])} nos 12 anteriores ({(rm - 1) * 100:+.0f}%), enquanto o estado "
                    f"variou {(rs - 1) * 100:+.0f}%. Diferença descritiva; não indica causa nem "
                    "considera mudanças de registro locais."
                ),
                metricas={
                    "anterior": int(r["a"]),
                    "atual": int(r["b"]),
                    "variacao_pct": round((rm - 1) * 100, 1),
                    "variacao_estado_pct": round((rs - 1) * 100, 1),
                    "z": round(z, 2),
                },
                forca=round(abs(z), 2),
            )
        )
    return sorted(itens, key=lambda i: -i.forca)


def _anomalias(categoria, cd_ibge, ref_semana: date) -> list[RadarItem]:
    db.require("anomalias")
    w, p = "", []
    if categoria:
        w += " AND a.categoria = ?"
        p.append(categoria)
    if cd_ibge is not None:
        w += " AND a.id = ?"
        p.append(str(cd_ibge))
    recentes = ref_semana - timedelta(weeks=ANOM_SEMANAS - 1)
    rows = db.query(
        f"""SELECT a.id, a.categoria, m.municipio, m.cd_ibge,
                   count(*) FILTER (WHERE a.semana > ? - INTERVAL 56 DAY) AS semanas_8,
                   max(a.semana) AS ultima, max(a.z) AS z_max,
                   arg_max(a.n, a.z)::INTEGER AS n, arg_max(a.esperado, a.z) AS esperado,
                   arg_max(a.semana, a.z) AS semana_pico
            FROM anomalias a JOIN municipios m ON a.id = CAST(m.cd_ibge AS VARCHAR)
            WHERE a.nivel = 'municipio' {w}
            GROUP BY ALL HAVING max(a.semana) >= ?
            ORDER BY z_max DESC""",
        [ref_semana, *p, recentes],
    )
    itens = []
    for r in rows:
        rec = r["semanas_8"] >= ANOM_RECORRENTE
        itens.append(
            RadarItem(
                tipo="anomalia",
                categoria=r["categoria"],
                categoria_nome=NOMES.get(r["categoria"]),
                cd_ibge=r["cd_ibge"],
                municipio=r["municipio"],
                periodo_inicio=r["semana_pico"],
                periodo_fim=r["semana_pico"] + timedelta(days=6),
                direcao="alta",
                titulo=(
                    f"{NOMES[r['categoria']]}: "
                    f"{'picos semanais recorrentes' if rec else 'pico semanal isolado'}"
                ),
                explicacao=(
                    f"Semana de {_fmt(r['semana_pico'])}: {r['n']} registros vs. ~"
                    f"{r['esperado']:.0f} esperados. Sinalizado em {r['semanas_8']} das últimas "
                    "8 semanas completas. Picos isolados costumam refletir eventos de massa ou "
                    "lotes de registro."
                ),
                metricas={
                    "n": r["n"],
                    "esperado": r["esperado"],
                    "z": r["z_max"],
                    "semanas_sinalizadas_8": r["semanas_8"],
                },
                forca=round(r["z_max"], 2),
            )
        )
    return itens


def _dados(categoria) -> list[RadarItem]:
    itens = []
    if db.has("qualidade_semana"):
        for r in db.query(
            "SELECT * FROM qualidade_semana WHERE status <> 'completa' ORDER BY semana"
        ):
            itens.append(
                RadarItem(
                    tipo="dados",
                    categoria=None,
                    categoria_nome=None,
                    cd_ibge=None,
                    municipio=None,
                    periodo_inicio=r["semana"],
                    periodo_fim=r["semana"] + timedelta(days=6),
                    titulo=f"Semana de {_fmt(r['semana'])} ainda {r['status']}",
                    explicacao=(
                        f"{r['registros']} registros, {r['razao'] * 100:.0f}% do volume típico "
                        "(mediana das 8 semanas anteriores). Fica fora de tendências, comparações "
                        "e alertas até completar; quedas aparentes nela não são reais."
                    ),
                    metricas={"registros": r["registros"], "razao": r["razao"]},
                    forca=round(1 - r["razao"], 3),
                )
            )
    if categoria and db.has("qualidade_categoria"):
        rows = db.query(
            "SELECT ano, coord_valida_pct, registros FROM qualidade_categoria "
            "WHERE categoria = ? ORDER BY ano DESC LIMIT 1",
            [categoria],
        )
        if rows and rows[0]["coord_valida_pct"] < COBERTURA_MAPA_MIN:
            r = rows[0]
            itens.append(
                RadarItem(
                    tipo="dados",
                    categoria=categoria,
                    categoria_nome=NOMES.get(categoria),
                    cd_ibge=None,
                    municipio=None,
                    periodo_inicio=date(r["ano"], 1, 1),
                    periodo_fim=date(r["ano"], 12, 31),
                    titulo=f"{NOMES[categoria]}: mapa cobre só {r['coord_valida_pct']:.0f}% dos registros",
                    explicacao=(
                        f"No arquivo de {r['ano']}, apenas {r['coord_valida_pct']:.0f}% dos "
                        "registros têm coordenada utilizável. O mapa mostra uma fração; use "
                        "séries e taxas por município para esta categoria."
                    ),
                    metricas={"coord_valida_pct": r["coord_valida_pct"]},
                    forca=round(100 - r["coord_valida_pct"], 1),
                )
            )
    return itens


@router.get("/radar", response_model=RadarResponse)
def radar(
    categoria: str | None = Query(None, pattern=CATS),
    cd_ibge: int | None = Query(None, description="Restringe a um município."),
    por_tipo: int = Query(6, ge=1, le=30, description="Máximo de itens por tipo."),
) -> RadarResponse:
    db.require("mudancas", "mudancas_avaliacao", "anomalias")
    ate = completo_ate()
    ref_semana = ate - timedelta(days=6)
    grupos = {
        "mudanca_persistente": _mudancas(categoria, cd_ibge, ate),
        "variacao": _variacoes(categoria, cd_ibge, ultimo_mes_completo(ate)),
        "anomalia": _anomalias(categoria, cd_ibge, ref_semana),
        "dados": _dados(categoria),
    }
    itens = [i for g in grupos.values() for i in g[:por_tipo]]
    return RadarResponse(
        referencia=ate,
        criterios=CRITERIOS,
        contagem={k: len(v) for k, v in grupos.items()},
        itens=itens,
        aviso=(
            "Observações estatísticas sobre registros policiais, não sobre crime real. Nenhum "
            "item indica causa; todos pedem investigação com outras fontes."
        ),
    )


@router.get("/mudancas", response_model=MudancasResponse)
def mudancas(
    categoria: str | None = Query(None, pattern=CATS),
    cd_ibge: int | None = None,
) -> MudancasResponse:
    db.require("mudancas", "mudancas_avaliacao")
    aval = avaliacao_por_categoria()
    w, p = _filtros(categoria, cd_ibge, "d.")
    rows = db.query(
        f"""SELECT d.cd_ibge, m.municipio, d.categoria, d.direcao, d.inicio, d.semanas,
                   d.razao, d.observado::INTEGER AS observado, d.esperado
            FROM mudancas d JOIN municipios m USING (cd_ibge) WHERE TRUE {w}
            ORDER BY d.cusum_max DESC""",
        p,
    )
    sim = db.query(
        "SELECT nivel_semanal::DOUBLE AS nivel_semanal, cenario, "
        "cusum_taxa_sinal::DOUBLE AS cusum_taxa_sinal, "
        "referencia_taxa_sinal::DOUBLE AS referencia_taxa_sinal, "
        "cusum_atraso_medio_semanas::DOUBLE AS cusum_atraso_medio_semanas "
        "FROM mudancas_avaliacao WHERE tipo = 'simulacao' "
        "ORDER BY nivel_semanal, cenario"
    )
    return MudancasResponse(
        referencia=completo_ate(),
        metodo=CRITERIOS["mudanca_persistente"],
        itens=[
            Mudanca(**r, confiavel=aval.get(r["categoria"], {}).get("confiavel", False))
            for r in rows
        ],
        avaliacao=[
            AvaliacaoCategoria(
                categoria=c,
                series_avaliadas=int(a["series_avaliadas"] or 0),
                sinais=int(a["cusum_sinais"] or 0),
                confirmados_pct=a["cusum_confirmados_pct"],
                confirmacao_acaso_pct=a["cusum_confirmacao_acaso_pct"],
                referencia_confirmados_pct=a["referencia_confirmados_pct"],
                referencia_confirmacao_acaso_pct=a["referencia_confirmacao_acaso_pct"],
                confiavel=a["confiavel"],
            )
            for c, a in sorted(aval.items())
        ],
        simulacao=[Simulacao(**s) for s in sim],
    )
