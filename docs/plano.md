# Plano em fases — SinalBR

Fontes confirmadas (testadas em 2026-10-10):
- SSP-SP: `https://www.ssp.sp.gov.br/assets/estatistica/transparencia/spDados/SPDadosCriminais_{ano}.xlsx` (2022–2026, ~200 MB/ano, ~1,16 mi BOs/ano). Dicionário na aba `CAMPOS_DA_TABELA_SPDADOS`.
- IBGE malha: `https://servicodados.ibge.gov.br/api/v3/malhas/estados/35?intrarregiao=municipio&formato=application/vnd.geo+json`
- IBGE população (Censo 2022): `https://servicodados.ibge.gov.br/api/v3/agregados/4714/periodos/2022/variaveis/93?localidades=N6[N3[35]]`

| Fase | Entrega | Critério de pronto |
|---|---|---|
| 1 ✅ | Pipeline bronze/silver/gold + API mínima + mapa de calor no navegador | Dados reais 2022–2026 ingeridos; relatório de qualidade; H3 com k-mínimo; mapa exibe células |
| 2 ✅ | Análises: temporal, comparação normalizada, anomalias | Endpoints + testes; resultados validados |
| 3 | Previsão de risco com backtesting | Baseline vs. modelo, métricas honestas |
| 4 | Landing, dashboard completo, PDF/CSV, dark mode, a11y | Lighthouse a11y razoável |
| 5 | Docker, CI, pre-commit, README com screenshots | CI verde |
