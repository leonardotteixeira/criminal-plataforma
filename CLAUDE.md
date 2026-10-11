# SinalBR — convenções do projeto

Plataforma de inteligência criminal com dados abertos e agregados (SSP-SP + IBGE). Marca provisória: troque em `web/src/config/brand.ts`.

## Regras inegociáveis
- **Nunca** ingerir/persistir dados pessoais: logradouro, número, `NUM_BO`, coordenadas brutas. Ver `docs/privacidade.md`.
- Toda exibição aplica k-mínimo (`K_MIN=5`). A API lê só tabelas gold.
- Avisos de limitação (subnotificação, viés de policiamento) devem aparecer na UI e no README.
- Sem dados fictícios: se uma fonte falhar, dizer explicitamente.

## Estrutura
- `data/` pipeline Python (uv): `bronze.py` → `silver.py` → `gold.py`, `quality.py`, `ibge.py`. Lake em `data/lake/` (git-ignorado).
- `api/` FastAPI + DuckDB lendo Parquet gold. `web/` Next.js + Tailwind + MapLibre/deck.gl.
- `docs/` plano, privacidade, qualidade dos dados.

## Comandos
- Pipeline: `cd data && uv run python -m sinalbr_data [bronze|silver|gold|analytics|forecast|quality|all]`
- API: `cd api && uv run uvicorn app.main:app --port 8000`; testes `uv run pytest`
- Web: `cd web && npm run dev`; `npx tsc --noEmit && npx eslint src`
- Lint Python: `uv run ruff check . && uv run ruff format .`

## Convenções
- Python 3.11 (sem sintaxe PEP 695). Código e identificadores de domínio em português; mensagens ao usuário em pt-BR.
- Arquivos em UTF-8; use `encoding="utf-8"` explícito (Windows).
- Neste ambiente Windows, `pandas`, `pyarrow` e `h3` são bloqueados por política de aplicativos: use DuckDB (inclui extensão `h3`) para I/O Parquet e H3.
- Schema da SSP-SP muda entre anos (aliases em `config.py`). Ao adicionar um ano/estado, atualizar aliases e o relatório de qualidade.
