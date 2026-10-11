import duckdb
import pytest

from sinalbr_data import config as C
from sinalbr_data.bronze import _norm_header
from sinalbr_data.silver import CATEGORIA_SQL

FORBIDDEN = {"LOGRADOURO", "NUMERO_LOGRADOURO", "NUM_BO", "LATITUDE", "LONGITUDE"}


def test_header_normalization_handles_mojibake_and_aliases():
    assert _norm_header("NOME_DELEGACIA_CIRCUNCRIÇÃO") == "NOME_DELEGACIA_CIRCUNCRICAO"
    assert _norm_header("NOME_DELEGACIA_CIRCUNCRI��O") == "NOME_DELEGACIA_CIRCUNCRIO"
    assert _norm_header("COD IBGE") == "CD_IBGE"


def test_personal_identifiers_are_never_kept():
    assert not FORBIDDEN & set(C.KEEP_COLUMNS) - {"LATITUDE", "LONGITUDE"}
    assert "LOGRADOURO" not in C.KEEP_COLUMNS and "NUM_BO" not in C.KEEP_COLUMNS


@pytest.mark.parametrize(
    ("natureza", "categoria"),
    [
        ("ROUBO - OUTROS", "roubo"),
        ("ROUBO DE VEICULO", "roubo"),
        ("LATROCINIO", "roubo"),
        ("FURTO DE VEICULO", "furto"),
        ("HOMICIDIO DOLOSO", "homicidio"),
        ("TENTATIVA DE HOMICIDIO", "homicidio"),
        ("HOMICIDIO CULPOSO POR ACIDENTE DE TRANSITO", "transito"),
        ("LESAO CORPORAL DOLOSA", "lesao_corporal"),
        ("LESAO CORPORAL CULPOSA POR ACIDENTE DE TRANSITO", "transito"),
        ("ESTUPRO DE VULNERAVEL", "sexual"),
        ("TRAFICO DE ENTORPECENTES", "drogas"),
        ("PORTE DE ARMA", "armas"),
        ("ALGO NOVO", "outros"),
    ],
)
def test_category_mapping(natureza, categoria):
    got = duckdb.sql(f"SELECT {CATEGORIA_SQL} FROM (SELECT '{natureza}' AS natureza)").fetchone()[0]
    assert got == categoria


def test_silver_has_no_raw_coordinates_or_addresses():
    path = C.SILVER / "occurrences.parquet"
    if not path.exists():
        pytest.skip("silver não gerada")
    cols = {
        r[0].upper() for r in duckdb.sql(f"DESCRIBE SELECT * FROM '{path.as_posix()}'").fetchall()
    }
    assert not FORBIDDEN & cols
    assert "H3_8" in cols
