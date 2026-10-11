"""Camada bronze: baixa os XLSX da SSP-SP e grava Parquet com colunas minimizadas.

Idempotente e incremental: só baixa/reprocessa um ano se o tamanho/Last-Modified
remoto mudou desde a última execução (manifesto em raw/manifest.json).
"""

import csv
import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

import duckdb
import httpx
from python_calamine import CalamineWorkbook

from . import config as C


def _norm_header(h: str) -> str:
    h = unicodedata.normalize("NFKD", str(h)).encode("ascii", "ignore").decode()
    h = re.sub(r"[^A-Za-z0-9]+", "_", h.upper()).strip("_")
    return {"COD_IBGE": "CD_IBGE"}.get(h, h)


def _manifest() -> dict:
    p = C.RAW / "manifest.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _save_manifest(m: dict) -> None:
    (C.RAW / "manifest.json").write_text(json.dumps(m, indent=2), encoding="utf-8")


def remote_meta(year: int) -> dict:
    r = httpx.head(C.SSP_URL.format(year=year), follow_redirects=True, timeout=60)
    r.raise_for_status()
    return {
        "size": int(r.headers["content-length"]),
        "last_modified": r.headers.get("last-modified", ""),
    }


def download(year: int, meta: dict) -> Path:
    dest = C.RAW / "ssp" / f"SPDadosCriminais_{year}.xlsx"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size == meta["size"]:
        return dest
    tmp = dest.with_suffix(".part")
    with httpx.stream("GET", C.SSP_URL.format(year=year), follow_redirects=True, timeout=300) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk)
    tmp.replace(dest)
    return dest


def xlsx_to_csv(path: Path, csv_path: Path) -> int:
    """Lê as abas de dados e grava só as colunas permitidas em um CSV temporário."""
    wb = CalamineWorkbook.from_path(str(path))
    n = 0
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([*C.KEEP_COLUMNS, "SHEET"])
        for name in wb.sheet_names:
            if name.upper().startswith("CAMPOS"):
                continue
            rows = wb.get_sheet_by_name(name).to_python(skip_empty_area=False)
            if len(rows) < 2:
                continue
            cols = [_norm_header(h) for h in rows[0]]
            idx = []
            for c in C.KEEP_COLUMNS:
                found = next((a for a in C.COLUMN_ALIASES.get(c, [c]) if a in cols), None)
                if found is None and c not in C.OPTIONAL_COLUMNS:
                    raise ValueError(f"{path.name}/{name}: coluna obrigatoria ausente {c}")
                idx.append(cols.index(found) if found else None)
            for r in rows[1:]:
                w.writerow([r[i] if i is not None else "" for i in idx] + [name])
            n += len(rows) - 1
            print(f"  {name}: {len(rows) - 1:,} linhas", flush=True)
    return n


def run(years: list[int] | None = None, force: bool = False) -> None:
    C.BRONZE.mkdir(parents=True, exist_ok=True)
    years = years or list(range(C.FIRST_YEAR, datetime.now().year + 1))
    manifest = _manifest()
    for year in years:
        try:
            meta = remote_meta(year)
        except httpx.HTTPError as e:
            print(f"[{year}] indisponivel na fonte ({e}); pulando")
            continue
        out = C.BRONZE / f"ssp_{year}.parquet"
        if not force and out.exists() and manifest.get(str(year)) == meta:
            print(f"[{year}] sem mudancas, pulando")
            continue
        print(f"[{year}] baixando ({meta['size'] / 1e6:.0f} MB)...", flush=True)
        path = download(year, meta)
        tmp_csv = C.RAW / f"ssp_{year}.csv"
        n = xlsx_to_csv(path, tmp_csv)
        ingested = datetime.now().isoformat(timespec="seconds")
        # Tudo como texto: a tipagem acontece na camada silver.
        duckdb.sql(
            f"""COPY (
                SELECT *, '{path.name}' AS _source_file,
                       '{meta["last_modified"]}' AS _source_modified,
                       '{ingested}' AS _ingested_at
                FROM read_csv('{tmp_csv.as_posix()}', all_varchar=true, header=true)
            ) TO '{out.as_posix()}' (FORMAT parquet, COMPRESSION zstd)"""
        )
        tmp_csv.unlink()
        manifest[str(year)] = meta
        _save_manifest(manifest)
        print(f"[{year}] bronze ok: {n:,} linhas -> {out.name}", flush=True)


if __name__ == "__main__":
    run([int(a) for a in sys.argv[1:]] or None)
