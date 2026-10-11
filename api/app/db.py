"""Acesso somente-leitura à camada gold (Parquet) via DuckDB, com cache TTL simples."""

import functools
import threading
import time

import duckdb

from .settings import CACHE_TTL, LAKE_DIR

_lock = threading.Lock()
_con: duckdb.DuckDBPyConnection | None = None
GOLD_TABLES = [
    "cell_month",
    "mun_month",
    "mun_week",
    "mun_hour_dow",
    "bairro_month",
    "cell_week",
    "anomalias",
    "meta",
]


def connection() -> duckdb.DuckDBPyConnection:
    global _con
    with _lock:
        if _con is None:
            _con = duckdb.connect()
            for t in GOLD_TABLES:
                p = (LAKE_DIR / "gold" / f"{t}.parquet").as_posix()
                _con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_parquet('{p}')")
            p = (LAKE_DIR / "ref" / "municipios_sp.parquet").as_posix()
            _con.execute(f"CREATE VIEW municipios AS SELECT * FROM read_parquet('{p}')")
    return _con


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
