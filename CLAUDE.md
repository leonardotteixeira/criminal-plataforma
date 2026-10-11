# SinalBR — convenções do projeto

Plataforma de inteligência criminal com dados abertos e agregados (SSP-SP + IBGE). Marca provisória: troque em `web/src/config/brand.ts`.

## Regras inegociáveis
- **Nunca** ingerir/persistir dados pessoais: logradouro, número, `NUM_BO`, coordenadas brutas. Ver `docs/privacidade.md`.
- Toda exibição aplica k-mínimo (`K_MIN=5`). A API lê só tabelas gold.
- Avisos de limitação (subnotificação, viés de policiamento) devem aparecer na UI e no README.
- Sem dados fictícios: se uma fonte falhar, dizer explicitamente.

## Estrutura
- `data/` pipeline Python (uv): `bronze.py` → `silver.py` → `gold.py` → `analytics.py` (anomalias, meta) → `changes.py` (mudanças persistentes + avaliação) → `forecast.py` → `quality.py` (tabelas de qualidade, histórico). Lake em `data/lake/` (git-ignorado).
- `api/` FastAPI + DuckDB lendo Parquet gold. Tabelas opcionais ausentes → 503 com a etapa a rodar (`db.require`). Rotas: `main.py`, `analysis.py`, `radar.py`, `qualidade.py`, `previsao.py`.
- `web/` Next.js + Tailwind + MapLibre/deck.gl. Páginas: `/`, `/dashboard`, `/radar`, `/comparar`, `/qualidade`, `/relatorio`. Componentes base em `components/ui.tsx` (Card, Notice, StateMessage, Delta, Badge); chamadas à API só via `lib/api.ts`; carregamento via `lib/useLoad.ts`.
- `docs/` plano, privacidade, qualidade, análises, previsão, `img/` (screenshots do README).

## Comandos
- Pipeline: `cd data && uv run python -m sinalbr_data [bronze|silver|gold|analytics|forecast|quality|all]`
- API: `cd api && uv run uvicorn app.main:app --port 8000`; testes `uv run pytest`
- Web: `cd web && npm run dev`; `npx tsc --noEmit && npx eslint src`
- Docker: `docker compose up --build` (pipeline → api → web). Pre-commit: `.pre-commit-config.yaml`. CI: `.github/workflows/ci.yml`.
- Lint Python: `uv run ruff check . && uv run ruff format .`

## Convenções
- Variações de registros usam seta + texto em cor neutra (`Delta`): aumento de registros nunca é "verde". Cores semânticas: `danger`, `warning`, `info`; séries em paleta Okabe-Ito com traços diferentes.
- Estado de telas analíticas vai para a URL (compartilhável e salvável).
- Toda nova análise: critérios explícitos, sem linguagem causal, estado vazio explicativo e teste.
- Python 3.11 (sem sintaxe PEP 695). Código e identificadores de domínio em português; mensagens ao usuário em pt-BR.
- Arquivos em UTF-8; use `encoding="utf-8"` explícito (Windows).
- Neste ambiente Windows, `pandas`, `pyarrow` e `h3` são bloqueados por política de aplicativos: use DuckDB (inclui extensão `h3`) para I/O Parquet e H3.
- Schema da SSP-SP muda entre anos (aliases em `config.py`). Ao adicionar um ano/estado, atualizar aliases e o relatório de qualidade.
