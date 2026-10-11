"""Monitor de qualidade dos dados: lê as tabelas geradas pelo pipeline (não recalcula nada)."""

from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel, Field

from . import db

router = APIRouter(prefix="/v1", tags=["qualidade"])


class QualidadeAno(BaseModel):
    ano: int = Field(description="Arquivo anual da SSP (ano de registro).")
    registros: int
    coord_valida_pct: float
    coord_zero_pct: float = Field(
        description="Coordenada 0/ocultada pela fonte (ex.: crimes sexuais)."
    )
    coord_ausente_pct: float
    coord_invalida_pct: float = Field(description="Fora do estado ou do município informado.")
    sem_hora_pct: float
    data_imputada_pct: float = Field(
        description="Data do fato inválida, substituída pela de registro."
    )
    sem_bairro_pct: float
    sem_tipo_local_pct: float
    nao_classificado_pct: float
    fora_da_janela: int = Field(description="Fatos fora da janela analisada (excluídos do gold).")
    tamanho_mb: float | None = Field(
        description="Nulo quando o manifesto da fonte não está disponível."
    )
    fonte_modificada: str | None


class QualidadeCategoria(BaseModel):
    ano: int
    categoria: str
    registros: int
    coord_valida_pct: float
    sem_hora_pct: float
    data_imputada_pct: float


class QualidadeSemana(BaseModel):
    semana: date
    registros: int
    mediana_8: float | None
    razao: float | None
    status: str = Field(description="completa (>= 85%), parcial (>= 10%) ou residual")


class Etapa(BaseModel):
    ordem: int
    etapa: str
    definicao: str
    registros: int


class Execucao(BaseModel):
    processado_em: str
    etapas: str
    fonte_atualizada_em: str | None
    dados_ate: str | None
    semana_completa_ate: str | None
    registros_silver: int | None


class QualidadeResponse(BaseModel):
    anos: list[QualidadeAno]
    categorias: list[QualidadeCategoria]
    semanas: list[QualidadeSemana]
    etapas: list[Etapa]
    execucoes: list[Execucao]
    definicoes: dict[str, str]


DEFINICOES = {
    "coord_valida_pct": "Coordenada dentro do estado e da caixa do município informado; usada no mapa.",
    "sem_hora_pct": "Hora do fato ausente; esses registros ficam fora da grade dia × hora.",
    "status_semana": (
        "Completa: total estadual >= 85% da mediana das 8 semanas anteriores. Parcial: entre 10% "
        "e 85% (atraso de registro). Residual: < 10% (registros soltos após o corte do arquivo)."
    ),
    "indisponivel": (
        "Um valor nulo significa que o indicador não pôde ser calculado (ex.: manifesto da fonte "
        "ausente), não que seja zero."
    ),
}


@router.get("/qualidade", response_model=QualidadeResponse)
def qualidade() -> QualidadeResponse:
    db.require(
        "qualidade_ano", "qualidade_categoria", "qualidade_semana", "qualidade_etapas", "execucoes"
    )
    return QualidadeResponse(
        anos=[QualidadeAno(**r) for r in db.query("SELECT * FROM qualidade_ano ORDER BY ano")],
        categorias=[
            QualidadeCategoria(**r)
            for r in db.query("SELECT * FROM qualidade_categoria ORDER BY ano, categoria")
        ],
        semanas=[
            QualidadeSemana(**r)
            for r in db.query("SELECT * FROM qualidade_semana ORDER BY semana DESC")
        ],
        etapas=[Etapa(**r) for r in db.query("SELECT * FROM qualidade_etapas ORDER BY ordem")],
        execucoes=[
            Execucao(
                **{
                    k: (str(v) if k != "registros_silver" and v is not None else v)
                    for k, v in r.items()
                }
            )
            for r in db.query("SELECT * FROM execucoes ORDER BY processado_em DESC LIMIT 20")
        ],
        definicoes=DEFINICOES,
    )
