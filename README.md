# SinalBR

Plataforma de inteligência criminal construída **somente com dados abertos, agregados e anonimizados** (SSP-SP + IBGE). Nome provisório; a marca é centralizada em `web/src/config/brand.ts`.

> **Status: Fases 1 a 4 concluídas** (pipeline, API, mapa de calor, análises, anomalias, previsão com backtest, landing, exportação PDF/CSV e testes de frontend, tudo com dados reais). Métodos em [`docs/analises.md`](docs/analises.md) e [`docs/previsao.md`](docs/previsao.md). Veja [`docs/plano.md`](docs/plano.md) para as próximas fases.

## Limitações — leia antes de usar

- **BOs refletem o registro, não o crime real.** Há subnotificação, que varia por tipo de crime e região.
- **Modelos preditivos podem reforçar vieses de policiamento.** Use as análises para entender padrões, nunca para decidir sobre pessoas.
- Dados agregados (hexágono H3 ~0,7 km², município) e com limite mínimo de 5 ocorrências por célula. Os meses mais recentes são parciais por atraso de registro.
- ~28% das ocorrências não têm coordenada utilizável (crimes sexuais têm o local ocultado pela própria SSP); elas entram nas contagens por município, mas não no mapa.

Detalhes em [`docs/privacidade.md`](docs/privacidade.md) e [`docs/qualidade-dados.md`](docs/qualidade-dados.md).

## Fontes (verificadas em 2026-10-10)

| Fonte | URL |
|---|---|
| SSP-SP, ocorrências 2022–2026 | `https://www.ssp.sp.gov.br/assets/estatistica/transparencia/spDados/SPDadosCriminais_{ano}.xlsx` |
| IBGE, malha municipal | `https://servicodados.ibge.gov.br/api/v3/malhas/estados/35` |
| IBGE, população (Censo 2022) | `https://servicodados.ibge.gov.br/api/v3/agregados/4714/periodos/2022/variaveis/93` |

## Arquitetura

```
SSP-SP xlsx ──► bronze (Parquet, colunas mínimas) ──► silver (tipada, H3, sem coordenadas)
                                                          │
IBGE (malha, população) ───────────────────────────────►  gold (agregados H3/município/bairro × mês × crime)
                                                          │
                                         FastAPI + DuckDB (k-mínimo, cache, OpenAPI)
                                                          │
                                         Next.js + MapLibre/deck.gl (painel)
```

## Como rodar

Pré-requisitos: Python 3.11+, [uv](https://docs.astral.sh/uv/), Node 20+.

```bash
# 1. Pipeline (baixa ~1 GB de XLSX; leva ~15 min)
cd data && uv sync && uv run python -m sinalbr_data all

# 2. API (http://localhost:8000/docs)
cd ../api && uv sync && uv run uvicorn app.main:app --port 8000

# 3. Web (http://localhost:3000)
cd ../web && npm install && npm run dev
```

Testes: `cd data && uv run pytest`, `cd api && uv run pytest`, `cd web && npm test`.

**Exportação:** no painel, "Relatório (PDF)" abre uma página imprimível (mapa estático, série, ranking e limitações; use *Imprimir → Salvar como PDF*) e "CSV" baixa o ranking por município (`/v1/export/municipios.csv` e `/v1/export/celulas.csv`, UTF-8 com BOM, já com supressão k-mínimo).

## Decisões técnicas

- **DuckDB + Parquet** em vez de PostGIS: volume (~5,5 mi linhas) cabe em um arquivo e as consultas são agregações; o H3 vem da extensão `h3` do DuckDB.
- **Coordenadas não são persistidas**: só o hexágono H3 (res. 8) sobrevive à camada silver.
- **Ingestão incremental**: um ano só é reprocessado se o tamanho/`Last-Modified` remoto mudou.
- O layout dos arquivos da SSP muda entre anos (ex.: 2022 usa `CIDADE`); a ingestão resolve por aliases e falha alto se faltar coluna obrigatória.

## Ainda não implementado

Docker Compose, CI, pre-commit, screenshots e diagrama final (Fase 5).
