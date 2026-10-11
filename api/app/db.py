"""Acesso somente-leitura à camada gold (Parquet) via DuckDB, com cache TTL simples.

A API só enxerga tabelas agregadas. `bairro_month` existe no lake mas não é exposta: bairro é uma
granularidade mais sensível e nenhuma tela precisa dela.
"""

import functools
import threading
import time

import duckdb
from fastapi import HTTPException

from .settings import CACHE_TTL, LAKE_DIR

_lock = threading.Lock()
_con: duckdb.DuckDBPyConnection | None = None
_available: set[str] = set()

# Sem estas a API não tem o que servir: falha na inicialização.
CORE_TABLES = ["cell_month", "mun_month", "mun_week", "mun_hour_dow", "cell_week", "meta"]
# Produzidas por etapas específicas do pipeline; se faltarem, só o endpoint correspondente
# responde 503 explicando qual etapa rodar.
OPTIONAL_TABLES = {
    "anomalias": "analytics",
    "previsao": "forecast",
    "backtest": "forecast",
    "backtest_calibracao": "forecast",
    "mudancas": "changes",
    "mudancas_avaliacao": "changes",
    "qualidade_ano": "quality",
    "qualidade_categoria": "quality",
    "qualidade_semana": "quality",
    "qualidade_etapas": "quality",
    "execucoes": "quality",
}
GOLD_TABLES = CORE_TABLES + list(OPTIONAL_TABLES)


def connection() -> duckdb.DuckDBPyConnection:
    global _con
    with _lock:
        if _con is None:
            con = duckdb.connect()
            for t in GOLD_TABLES:
                path = LAKE_DIR / "gold" / f"{t}.parquet"
                if not path.exists():
                    if t in CORE_TABLES:
                        raise RuntimeError(f"tabela gold obrigatória ausente: {path}")
                    continue
                con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_parquet('{path.as_posix()}')")
                _available.add(t)
            p = (LAKE_DIR / "ref" / "municipios_sp.parquet").as_posix()
            con.execute(f"CREATE VIEW municipios AS SELECT * FROM read_parquet('{p}')")
            _con = con
    return _con


def require(*tables: str) -> None:
    """503 explícito quando uma tabela opcional não foi gerada (em vez de erro 500 genérico)."""
    connection()
    missing = [t for t in tables if t not in _available]
    if missing:
        etapas = sorted({OPTIONAL_TABLES.get(t, "?") for t in missing})
        raise HTTPException(
            503,
            f"Dados indisponíveis ({', '.join(missing)}). Rode a etapa do pipeline: "
            f"python -m sinalbr_data {' / '.join(etapas)}",
        )


def has(table: str) -> bool:
    connection()
    return table in _available


def query(sql: str, params: list | None = None) -> list[dict]:
    cur = connection().cursor()
    cur.execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]


def ttl_cache(fn):
    store: dict = {}

    @functools.wraps(fn)
    def wrapper(*args):
        hit = store.get(args)
        if hit and time.monotonic() - hit[0] < CACHE_TTL:
            return hit[1]
        val = fn(*args)
        store[args] = (time.monotonic(), val)
        return val

    return wrapper
