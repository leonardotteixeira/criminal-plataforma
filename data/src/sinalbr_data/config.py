"""Configuração central do pipeline (caminhos, fontes, parâmetros de privacidade)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "raw"
LAKE = ROOT / "lake"
BRONZE = LAKE / "bronze"
SILVER = LAKE / "silver"
GOLD = LAKE / "gold"
REPORTS = LAKE / "reports"
DB_PATH = LAKE / "sinalbr.duckdb"

SSP_URL = "https://www.ssp.sp.gov.br/assets/estatistica/transparencia/spDados/SPDadosCriminais_{year}.xlsx"
IBGE_MALHA_URL = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/estados/35"
    "?intrarregiao=municipio&formato=application/vnd.geo+json&qualidade=minima"
)
IBGE_POP_URL = (
    "https://servicodados.ibge.gov.br/api/v3/agregados/4714/periodos/2022/variaveis/93"
    "?localidades=N6[N3[35]]"
)
IBGE_MUN_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/35/municipios"
FIRST_YEAR = 2022

# Privacidade: células com menos ocorrências que K_MIN nunca são expostas.
K_MIN = 5
H3_RES = 8  # ~0,74 km² por hexágono

# Caixa envolvente do estado de SP, usada para validar coordenadas.
SP_BBOX = {"lat": (-25.4, -19.7), "lon": (-53.2, -44.1)}

# Colunas mantidas do arquivo original. LOGRADOURO, NUMERO_LOGRADOURO e NUM_BO são
# descartados na ingestão (minimização de dados, ver docs/privacidade.md).
KEEP_COLUMNS = [
    "NOME_DELEGACIA",
    "NOME_MUNICIPIO",
    "ANO_BO",
    "DATA_REGISTRO",
    "DATA_OCORRENCIA_BO",
    "HORA_OCORRENCIA_BO",
    "DESC_PERIODO",
    "DESCR_TIPOLOCAL",
    "BAIRRO",
    "LATITUDE",
    "LONGITUDE",
    "RUBRICA",
    "NATUREZA_APURADA",
    "CD_IBGE",
]

# O layout da SSP-SP mudou entre anos (ex.: 2022 usa CIDADE/DATA_COMUNICACAO_BO).
# Cada coluna canônica aceita aliases; colunas opcionais ausentes viram NULL.
COLUMN_ALIASES = {
    "NOME_MUNICIPIO": ["NOME_MUNICIPIO", "CIDADE"],
    "DATA_REGISTRO": ["DATA_REGISTRO", "DATA_COMUNICACAO_BO"],
    "DESC_PERIODO": ["DESC_PERIODO", "DESCR_PERIODO"],
}
OPTIONAL_COLUMNS = {"DESCR_TIPOLOCAL", "DESC_PERIODO", "CD_IBGE"}
