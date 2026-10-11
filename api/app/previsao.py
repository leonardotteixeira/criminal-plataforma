"""Previsão de risco (próximas 4 semanas, hexágonos H3 res. 7) e resultados do backtest."""

from datetime import date

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from . import db

router = APIRouter(prefix="/v1/previsao", tags=["previsao"])

AVISO = (
    "Previsão de ocorrências REGISTRADAS, não de crime real. Áreas mais policiadas ou com mais "
    "registro tendem a aparecer como de maior risco (viés de feedback). Não use para decisões "
    "sobre pessoas. A faixa é relativa dentro do tipo de crime e das células com histórico."
)


class PrevisaoCell(BaseModel):
    h3: str = Field(description="Índice H3 resolução 7 (~5 km²).")
    esperado_4s: float = Field(description="Registros esperados nas próximas 4 semanas.")
    faixa: str = Field(description="alta (top 10%), media (10–30%) ou baixa.")


class PrevisaoResponse(BaseModel):
    categoria: str
    origem: date
    inicio_previsao: date
    fim_previsao: date
    celulas: list[PrevisaoCell]
    aviso: str


class ModeloMetrica(BaseModel):
    modelo: str
    desvio_poisson: float = Field(description="Menor é melhor.")
    mae: float
    captura_top10: float = Field(
        description="Fração dos eventos reais nas 10% células de maior previsão."
    )
    origens_melhor_que_media12_pct: float
    n_obs: int
    n_origens: int


class Decil(BaseModel):
    decil: int
    previsto: float
    observado: float


class BacktestResponse(BaseModel):
    categoria: str
    metodo: str
    modelos: list[ModeloMetrica]
    calibracao: list[Decil]
    reducao_desvio_vs_media12_pct: float
    ganho_captura_vs_media12_pp: float
    captura_teto_oraculo: float
    leitura: str


@router.get("/h3", response_model=PrevisaoResponse)
def previsao(categoria: str = Query("roubo", pattern="^(roubo|furto|lesao_corporal)$")):
    db.require("previsao")
    rows = db.query(
        "SELECT h3, esperado_4s, faixa, origem, inicio_previsao, fim_previsao "
        "FROM previsao WHERE categoria = ? ORDER BY esperado_4s DESC",
        [categoria],
    )
    if not rows:
        raise HTTPException(404, "sem previsão para a categoria")
    r0 = rows[0]
    return PrevisaoResponse(
        categoria=categoria,
        origem=r0["origem"],
        inicio_previsao=r0["inicio_previsao"],
        fim_previsao=r0["fim_previsao"],
        celulas=[
            PrevisaoCell(h3=r["h3"], esperado_4s=r["esperado_4s"], faixa=r["faixa"]) for r in rows
        ],
        aviso=AVISO,
    )


@router.get("/backtest", response_model=BacktestResponse)
def backtest(categoria: str = Query("roubo", pattern="^(roubo|furto|lesao_corporal)$")):
    db.require("backtest", "backtest_calibracao")
    rows = db.query(
        "SELECT modelo, desvio_poisson, mae, captura_top10, origens_melhor_que_media12_pct, "
        "n_obs, n_origens FROM backtest WHERE categoria = ? ORDER BY desvio_poisson DESC",
        [categoria],
    )
    cal = db.query(
        "SELECT decil, previsto, observado FROM backtest_calibracao WHERE categoria = ? ORDER BY decil",
        [categoria],
    )
    if not rows:
        raise HTTPException(404, "sem backtest para a categoria")
    by = {r["modelo"]: r for r in rows}
    glm, base, oraculo = by["glm_viz"], by["media12"], by["oraculo"]
    red = round((1 - glm["desvio_poisson"] / base["desvio_poisson"]) * 100, 1)
    ganho = round((glm["captura_top10"] - base["captura_top10"]) * 100, 2)
    return BacktestResponse(
        categoria=categoria,
        metodo=(
            "Origem móvel: 6 refits (a cada 4 semanas) nas últimas 24 semanas completas, treinando "
            "só com origens cujo alvo (soma das 4 semanas seguintes) já havia terminado. "
            "Baselines: persistência (últimas 4 sem.), média de 12 semanas, mesma época do ano anterior."
        ),
        modelos=[ModeloMetrica(**r) for r in rows if r["modelo"] != "oraculo"],
        calibracao=[Decil(**c) for c in cal],
        reducao_desvio_vs_media12_pct=red,
        ganho_captura_vs_media12_pp=ganho,
        captura_teto_oraculo=oraculo["captura_top10"],
        leitura=(
            f"O modelo reduz o erro de contagem (desvio de Poisson) em {red}% frente à média de 12 "
            f"semanas, mas o ganho em acertar QUAIS células concentram mais eventos é de apenas "
            f"{ganho} p.p. (teto teórico: {oraculo['captura_top10'] * 100:.1f}%). Os pontos quentes "
            "são muito persistentes: uma média simples já os encontra."
        ),
    )
