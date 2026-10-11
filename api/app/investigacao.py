"""Ferramentas de investigação: decomposição das variações e robustez das conclusões.

Decomposição: quanto cada tipo de crime (ou município) contribuiu ARITMETICAMENTE para a variação
do total entre dois períodos. Contribuição não é causa.

Robustez: a conclusão "aumentou/diminuiu" se mantém quando mudamos a janela, comparamos com o
mesmo período do ano anterior, olhamos o estado e consideramos a incerteza? Mostra onde a
conclusão é frágil em vez de escondê-la.
"""

import math
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from . import db
from .analysis import _dispersao, _periodo_sum, completo_ate, shift_months, ultimo_mes_completo
from .settings import K_MIN

router = APIRouter(prefix="/v1", tags=["investigacao"])

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


def _janelas(meses: int) -> tuple[date, date, date, date]:
    """(ini_ant, fim_ant, ini, fim) com N meses completos e os N anteriores."""
    fim_mes = ultimo_mes_completo(completo_ate())
    ini = shift_months(fim_mes, -(meses - 1))
    ini_ant = shift_months(ini, -meses)
    fim = shift_months(fim_mes, 1) - timedelta(days=1)
    fim_ant = ini - timedelta(days=1)
    return ini_ant, fim_ant, ini, fim


# ---------------------------------------------------------------- decomposição
class Contribuicao(BaseModel):
    chave: str = Field(description="Categoria ou código IBGE ('demais' = agregado dos restantes).")
    nome: str
    anterior: int
    atual: int
    variacao_abs: int
    variacao_pct: float | None
    contribuicao_pct: float | None = Field(
        description="Parcela da variação total publicada (soma = 100%). Nula se a variação total é 0."
    )


class Decomposicao(BaseModel):
    por: str
    regiao: str
    categoria: str | None
    inicio_anterior: date
    fim_anterior: date
    inicio: date
    fim: date
    total_anterior: int
    total_atual: int
    variacao_total_pct: float | None
    itens: list[Contribuicao]
    nao_publicados: int = Field(description="Itens omitidos por terem < k em algum período.")
    nota: str


@router.get("/decomposicao", response_model=Decomposicao)
def decomposicao(
    por: str = Query("categoria", pattern="^(categoria|municipio)$"),
    categoria: str | None = Query(None, pattern=CATS),
    cd_ibge: int | None = Query(None, description="Município (só para por=categoria)."),
    meses: int = Query(12, ge=3, le=24),
    top: int = Query(10, ge=3, le=30, description="Municípios listados (por=municipio)."),
) -> Decomposicao:
    if por == "municipio" and not categoria:
        raise HTTPException(422, "por=municipio exige uma categoria")
    if por == "municipio" and cd_ibge is not None:
        raise HTTPException(422, "por=municipio decompõe o estado; não use cd_ibge")
    ini_ant, fim_ant, ini, fim = _janelas(meses)
    chave = "categoria" if por == "categoria" else "cd_ibge"
    where, params = "TRUE", []
    if por == "categoria" and cd_ibge is not None:
        where, params = "cd_ibge = ?", [cd_ibge]
    if por == "municipio":
        where, params = "categoria = ?", [categoria]
    rows = db.query(
        f"""SELECT {chave} AS k,
                   coalesce(sum(n) FILTER (WHERE mes BETWEEN ? AND ?), 0)::INTEGER AS a,
                   coalesce(sum(n) FILTER (WHERE mes BETWEEN ? AND ?), 0)::INTEGER AS b
            FROM mun_month WHERE {where} AND mes BETWEEN ? AND ? GROUP BY 1""",
        [ini_ant, fim_ant, ini, fim, *params, ini_ant, fim],
    )
    # Só itens publicáveis nos dois períodos (>= k). Os totais são a soma desses itens
    # (agregação consistente): nada pode ser recuperado por diferença.
    pub = [r for r in rows if r["a"] >= K_MIN and r["b"] >= K_MIN]
    nao_pub = len(rows) - len(pub)
    ta, tb = sum(r["a"] for r in pub), sum(r["b"] for r in pub)
    delta = tb - ta
    nomes = {}
    if por == "municipio":
        nomes = {
            m["cd_ibge"]: m["municipio"]
            for m in db.query("SELECT cd_ibge, municipio FROM municipios")
        }
    regiao = "Estado de São Paulo"
    if cd_ibge is not None:
        m = db.query("SELECT municipio FROM municipios WHERE cd_ibge = ?", [cd_ibge])
        if not m:
            raise HTTPException(404, f"município {cd_ibge} não encontrado")
        regiao = m[0]["municipio"]

    def item(k, nome, a, b) -> Contribuicao:
        return Contribuicao(
            chave=str(k), nome=nome, anterior=a, atual=b, variacao_abs=b - a,
            variacao_pct=round((b / a - 1) * 100, 1) if a else None,
            contribuicao_pct=round(100 * (b - a) / delta, 1) if delta else None,
        )  # fmt: skip

    pub.sort(key=lambda r: -abs(r["b"] - r["a"]))
    if por == "categoria":
        itens = [item(r["k"], NOMES.get(r["k"], r["k"]), r["a"], r["b"]) for r in pub]
    else:
        head, tail = pub[:top], pub[top:]
        itens = [item(r["k"], nomes.get(r["k"], str(r["k"])), r["a"], r["b"]) for r in head]
        if len(tail) >= 2:  # agregado só com 2+ membros (todos já publicáveis)
            itens.append(
                item(
                    "demais",
                    f"Demais {len(tail)} municípios",
                    sum(r["a"] for r in tail),
                    sum(r["b"] for r in tail),
                )
            )
    return Decomposicao(
        por=por,
        regiao=regiao,
        categoria=categoria,
        inicio_anterior=ini_ant,
        fim_anterior=fim_ant,
        inicio=ini,
        fim=fim,
        total_anterior=ta,
        total_atual=tb,
        variacao_total_pct=round((tb / ta - 1) * 100, 1) if ta else None,
        itens=itens,
        nao_publicados=nao_pub,
        nota=(
            "Decomposição aritmética: a soma das variações dos itens é a variação do total. "
            "Mostra onde a mudança se concentrou, não por que aconteceu. Totais incluem só itens "
            f"com ≥ {K_MIN} registros nos dois períodos."
        ),
    )


# ---------------------------------------------------------------- robustez
class Verificacao(BaseModel):
    nome: str
    descricao: str
    variacao_pct: float | None
    direcao: str | None = Field(description="alta | queda | estavel (|var| < 5%) | nulo")
    detalhe: str


class Robustez(BaseModel):
    regiao: str
    categoria: str
    veredito: str = Field(
        description="consistente | parcialmente_consistente | sensivel_a_janela | indistinguivel_do_ruido | insuficiente"
    )
    resumo: str
    verificacoes: list[Verificacao]
    cobertura: list[str] = Field(description="O que a cobertura dos dados permite ou não concluir.")


def _dir(v: float | None) -> str | None:
    if v is None:
        return None
    return "estavel" if abs(v) < 5 else ("alta" if v > 0 else "queda")


@router.get("/robustez", response_model=Robustez)
def robustez(
    categoria: str = Query(..., pattern=CATS),
    cd_ibge: int | None = None,
) -> Robustez:
    regiao = "Estado de São Paulo"
    if cd_ibge is not None:
        m = db.query("SELECT municipio FROM municipios WHERE cd_ibge = ?", [cd_ibge])
        if not m:
            raise HTTPException(404, f"município {cd_ibge} não encontrado")
        regiao = m[0]["municipio"]

    def var(a: int, b: int) -> float | None:
        if a < K_MIN or b < K_MIN:
            return None
        return round((b / a - 1) * 100, 1)

    checks: list[Verificacao] = []
    janelas_dir = []
    for meses in (6, 12, 24):
        ia, fa, ib, fb = _janelas(meses)
        a, b = _periodo_sum(categoria, cd_ibge, ia, fa), _periodo_sum(categoria, cd_ibge, ib, fb)
        v = var(a, b)
        janelas_dir.append(_dir(v))
        checks.append(
            Verificacao(
                nome=f"janela_{meses}m",
                descricao=f"Últimos {meses} meses completos vs. {meses} anteriores",
                variacao_pct=v,
                direcao=_dir(v),
                detalhe=f"{b} vs. {a} registros"
                if v is not None
                else f"menos de {K_MIN} registros",
            )
        )
    # mesmo trimestre do ano anterior (controla sazonalidade)
    fim_mes = ultimo_mes_completo(completo_ate())
    ib = shift_months(fim_mes, -2)
    fb = shift_months(fim_mes, 1) - timedelta(days=1)
    ia, fa = shift_months(ib, -12), shift_months(fim_mes, -11) - timedelta(days=1)
    a, b = _periodo_sum(categoria, cd_ibge, ia, fa), _periodo_sum(categoria, cd_ibge, ib, fb)
    v_saz = var(a, b)
    checks.append(
        Verificacao(
            nome="mesmo_trimestre_ano_anterior",
            descricao="Últimos 3 meses completos vs. os mesmos 3 meses do ano anterior",
            variacao_pct=v_saz,
            direcao=_dir(v_saz),
            detalhe=f"{b} vs. {a} registros"
            if v_saz is not None
            else f"menos de {K_MIN} registros",
        )
    )
    # 12 meses: incerteza e comparação com o estado
    ia, fa, ib, fb = _janelas(12)
    a, b = _periodo_sum(categoria, cd_ibge, ia, fa), _periodo_sum(categoria, cd_ibge, ib, fb)
    ruido = None
    if a >= K_MIN and b >= K_MIN:
        where, params = "categoria = ? AND mes BETWEEN ? AND ?", [categoria, ib, fb]
        if cd_ibge is not None:
            where += " AND cd_ibge = ?"
            params.append(cd_ibge)
        mensal = [
            r["n"]
            for r in db.query(
                f"SELECT mes, sum(n)::INTEGER AS n FROM mun_month WHERE {where} GROUP BY 1", params
            )
        ]
        phi = _dispersao(mensal)
        se = math.sqrt(phi * (1 / a + 1 / b))
        rr = b / a
        lo, hi = rr * math.exp(-1.96 * se), rr * math.exp(1.96 * se)
        ruido = lo <= 1 <= hi
        checks.append(
            Verificacao(
                nome="incerteza_12m",
                descricao="Intervalo de 95% da razão (12 meses), alargado pela superdispersão mensal",
                variacao_pct=round((rr - 1) * 100, 1),
                direcao=_dir((rr - 1) * 100),
                detalhe=f"razão {rr:.2f} (IC 95%: {lo:.2f} a {hi:.2f})"
                + ("; inclui 1: não se distingue da variação aleatória" if ruido else ""),
            )
        )
    if cd_ibge is not None:
        ea, eb = _periodo_sum(categoria, None, ia, fa), _periodo_sum(categoria, None, ib, fb)
        v_mun, v_est = var(a, b), var(ea, eb)
        dif = None if v_mun is None or v_est is None else round(v_mun - v_est, 1)
        checks.append(
            Verificacao(
                nome="relativo_ao_estado",
                descricao="Variação de 12 meses do município menos a do estado (pontos percentuais)",
                variacao_pct=dif,
                direcao=_dir(dif),
                detalhe=(
                    f"município {v_mun:+.1f}%, estado {v_est:+.1f}%"
                    if dif is not None
                    else "indisponível"
                ),
            )
        )

    principais = [d for d in janelas_dir if d is not None]
    if not principais or janelas_dir[1] is None:
        veredito = "insuficiente"
        resumo = (
            f"Poucos registros para avaliar a variação de {NOMES[categoria].lower()} em {regiao}."
        )
    elif ruido:
        veredito = "indistinguivel_do_ruido"
        resumo = "A variação de 12 meses não se distingue da oscilação aleatória esperada."
    elif {"alta", "queda"} <= set(principais) | ({_dir(v_saz)} - {None}):
        veredito = "sensivel_a_janela"
        resumo = (
            "A direção se inverte conforme a janela ou a comparação sazonal: a conclusão depende do "
            "recorte escolhido e não deve ser apresentada como tendência."
        )
    elif len(set(principais) | ({_dir(v_saz)} - {None})) > 1:
        veredito = "parcialmente_consistente"
        resumo = (
            "Nenhuma janela aponta a direção oposta, mas em algumas a variação fica abaixo de 5%. "
            "Se a janela curta (6 meses) está estável e as longas não, a mudança provavelmente já "
            "ocorreu e os registros se mantêm no novo patamar."
        )
    else:
        veredito = "consistente"
        resumo = (
            f"Todas as janelas e a comparação com o mesmo trimestre do ano anterior apontam "
            f"{'alta' if principais[0] == 'alta' else 'queda' if principais[0] == 'queda' else 'estabilidade'} "
            "de registros. Consistência não indica causa."
        )

    cobertura = []
    if db.has("qualidade_categoria"):
        q = db.query(
            "SELECT ano, coord_valida_pct, sem_hora_pct FROM qualidade_categoria WHERE categoria = ? "
            "ORDER BY ano DESC LIMIT 1",
            [categoria],
        )
        if q:
            r = q[0]
            cobertura.append(
                f"{r['coord_valida_pct']:.0f}% dos registros têm local utilizável ({r['ano']}): "
                + ("o mapa representa bem o tipo." if r["coord_valida_pct"] >= 80 else
                   "o mapa mostra só uma parte; não conclua sobre áreas sem pontos.")
            )  # fmt: skip
            cobertura.append(
                f"{r['sem_hora_pct']:.0f}% sem hora: "
                + ("a grade de horários é representativa." if r["sem_hora_pct"] <= 20 else
                   "padrões de horário valem só para os registros que informam a hora.")
            )  # fmt: skip
    cobertura.append(
        "Registros policiais: mudanças de registro e de policiamento afetam todas as verificações."
    )
    return Robustez(
        regiao=regiao, categoria=categoria, veredito=veredito, resumo=resumo,
        verificacoes=checks, cobertura=cobertura,
    )  # fmt: skip
