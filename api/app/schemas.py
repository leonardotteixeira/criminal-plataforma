from datetime import date
from typing import Generic, TypeVar

from pydantic import BaseModel, Field


class Meta(BaseModel):
    marca: str
    dados_ate: date = Field(
        description="Fim da última semana com volume não residual (ignora registros soltos)."
    )
    completo_ate: date = Field(description="Última data com dados considerados completos.")
    k_min: int = Field(description="Células com menos ocorrências que isso nunca são exibidas.")
    fonte_atualizada_em: str | None = Field(
        None, description="Data de modificação mais recente dos arquivos da SSP (versão da fonte)."
    )
    processado_em: str | None = Field(None, description="Quando o pipeline gerou os dados.")
    arredondamento_celulas: int = Field(
        description="Contagens de hexágono são múltiplos deste valor (proteção contra diferenciação)."
    )
    categorias: list[str]
    avisos: list[str]


class Categoria(BaseModel):
    id: str
    nome: str


class Cell(BaseModel):
    h3: str = Field(description="Índice H3 (resolução 8, ~0,7 km²).")
    n: int


class HeatmapResponse(BaseModel):
    inicio: date
    fim: date
    categoria: str | None
    k_min: int
    arredondamento: int = Field(description="Contagens arredondadas para múltiplos deste valor.")
    celulas_total: int
    celulas_suprimidas: int
    cells: list[Cell]


class MunicipioRef(BaseModel):
    cd_ibge: int
    municipio: str
    populacao_2022: int | None


class MunicipioRow(BaseModel):
    cd_ibge: int
    municipio: str
    populacao_2022: int | None
    ocorrencias: int | None = Field(description="Nulo quando suprimido (menor que k_min).")
    suprimido: bool
    taxa_100k: float | None = Field(description="Ocorrências por 100 mil hab. no período.")


T = TypeVar("T")


class Page(BaseModel, Generic[T]):  # noqa: UP046
    items: list[T]
    total: int
    page: int
    page_size: int


class SeriesPoint(BaseModel):
    periodo: date
    n: int | None = Field(description="Nulo quando suprimido (< k_min) numa série municipal.")
    suprimido: bool = False
    parcial: bool = Field(description="Mês ainda incompleto (atraso de registro).")


class HourDowCell(BaseModel):
    dow: int = Field(description="0 = domingo ... 6 = sábado")
    hora: int
    n: int | None = Field(description="Nulo = suprimido (< k_min); 0 = nenhum registro com hora.")
