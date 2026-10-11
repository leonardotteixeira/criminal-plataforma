"""Camada silver: tipagem, limpeza, normalização e anonimização espacial.

Decisão de privacidade: as coordenadas brutas NÃO são persistidas. Elas são usadas apenas
para validar o ponto e calcular o hexágono H3 (res. 8, ~0,7 km²); depois são descartadas.
"""

import duckdb

from . import config as C

CATEGORIA_SQL = """
CASE
  WHEN natureza LIKE 'ROUBO%' OR natureza LIKE 'LATROC%' OR natureza LIKE 'EXTORS%'
       THEN 'roubo'
  WHEN natureza LIKE 'FURTO%' THEN 'furto'
  WHEN natureza LIKE 'HOMIC%DOLOSO%' OR natureza LIKE 'TENTATIVA DE HOMIC%'
       OR natureza LIKE 'LESAO CORPORAL SEGUIDA DE MORTE%' THEN 'homicidio'
  WHEN natureza LIKE 'LESAO CORPORAL DOLOSA%' THEN 'lesao_corporal'
  WHEN natureza LIKE 'ESTUPRO%' THEN 'sexual'
  WHEN natureza LIKE '%ENTORPECENTES%' THEN 'drogas'
  WHEN natureza LIKE 'PORTE DE ARMA%' THEN 'armas'
  WHEN natureza LIKE '%ACIDENTE DE TRANSITO%' OR natureza LIKE '%CULPOS%' THEN 'transito'
  ELSE 'outros'
END
"""


def build_silver(con: duckdb.DuckDBPyConnection) -> None:
    C.SILVER.mkdir(parents=True, exist_ok=True)
    con.execute("INSTALL h3 FROM community; LOAD h3; INSTALL spatial; LOAD spatial;")
    geo = (C.LAKE / "ref" / "municipios_sp.geojson").as_posix()
    pop = (C.LAKE / "ref" / "municipios_sp.parquet").as_posix()
    lat_lo, lat_hi = C.SP_BBOX["lat"]
    lon_lo, lon_hi = C.SP_BBOX["lon"]
    con.execute(
        f"""
        CREATE OR REPLACE TABLE mun_bbox AS
        SELECT CAST(cd_ibge AS INTEGER) AS cd_ibge,
               ST_XMin(geom) AS xmin, ST_XMax(geom) AS xmax,
               ST_YMin(geom) AS ymin, ST_YMax(geom) AS ymax
        FROM ST_Read('{geo}')
        """
    )
    con.execute(
        f"""
        CREATE OR REPLACE TABLE stg AS
        WITH b AS (
          SELECT
            CAST(regexp_extract(_source_file, '([0-9]{{4}})', 1) AS INTEGER) AS source_year,
            TRY_CAST(substr(NULLIF(DATA_OCORRENCIA_BO, 'NULL'), 1, 10) AS DATE) AS d_ocor,
            TRY_CAST(substr(NULLIF(DATA_REGISTRO, 'NULL'), 1, 10) AS DATE) AS d_reg,
            TRY_CAST(split_part(NULLIF(HORA_OCORRENCIA_BO, 'NULL'), ':', 1) AS INTEGER) AS hora0,
            TRY_CAST(CD_IBGE AS DOUBLE)::INTEGER AS cd_ibge,
            NULLIF(upper(trim(BAIRRO)), 'NULL') AS bairro,
            NULLIF(trim(DESCR_TIPOLOCAL), 'NULL') AS tipo_local,
            strip_accents(upper(trim(coalesce(
              NULLIF(NATUREZA_APURADA, 'NULL'), NULLIF(RUBRICA, 'NULL'), 'NAO INFORMADO'
            )))) AS natureza,
            TRY_CAST(LATITUDE AS DOUBLE) AS lat,
            TRY_CAST(LONGITUDE AS DOUBLE) AS lon
          FROM read_parquet('{(C.BRONZE / "ssp_*.parquet").as_posix()}')
        )
        SELECT b.*, m.xmin, m.xmax, m.ymin, m.ymax,
          CASE
            WHEN lat IS NULL OR lon IS NULL THEN 'ausente'
            WHEN lat = 0 OR lon = 0 THEN 'ocultado_ou_zero'
            WHEN lat NOT BETWEEN {lat_lo} AND {lat_hi}
              OR lon NOT BETWEEN {lon_lo} AND {lon_hi} THEN 'fora_do_estado'
            WHEN m.cd_ibge IS NOT NULL AND (
                 lon < m.xmin - 0.02 OR lon > m.xmax + 0.02
              OR lat < m.ymin - 0.02 OR lat > m.ymax + 0.02) THEN 'fora_do_municipio'
            ELSE 'valida'
          END AS geo_status
        FROM b LEFT JOIN mun_bbox m USING (cd_ibge)
        """
    )
    out = (C.SILVER / "occurrences.parquet").as_posix()
    con.execute(
        f"""
        COPY (
          SELECT
            source_year,
            CASE WHEN d_ocor IS NULL OR d_ocor > current_date OR d_ocor < DATE '2000-01-01'
                 THEN d_reg ELSE d_ocor END AS data_fato,
            (d_ocor IS NULL OR d_ocor > current_date
                 OR d_ocor < DATE '2000-01-01') AS data_imputada,
            d_reg AS data_registro,
            CASE WHEN hora0 BETWEEN 0 AND 23 THEN hora0 END AS hora,
            s.cd_ibge, p.municipio,
            bairro, tipo_local, natureza,
            {CATEGORIA_SQL} AS categoria,
            geo_status,
            CASE WHEN geo_status = 'valida'
                 THEN h3_latlng_to_cell(lat, lon, {C.H3_RES}) END AS h3_8
          FROM stg s LEFT JOIN read_parquet('{pop}') p USING (cd_ibge)
        ) TO '{out}' (FORMAT parquet, COMPRESSION zstd)
        """
    )
    con.execute("DROP TABLE stg")
