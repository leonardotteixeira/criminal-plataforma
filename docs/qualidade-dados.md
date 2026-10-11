# Relatório de qualidade de dados (SSP-SP)

Gerado em 2026-10-10T22:34:57 a partir dos arquivos oficiais da SSP-SP.

| Arquivo | Registros | Coord. válida | Coord. 0/ocultada | Sem coord. | Fora do município | Sem hora | Data imputada | Sem município | Sem bairro |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2022 | 1,197,973 | 69.5% | 18.2% | 10.1% | 0.1% | 32.7% | 2.2% | 0.0% | 1.7% |
| 2023 | 1,241,911 | 72.6% | 17.2% | 10.0% | 0.1% | 30.0% | 0.2% | 0.0% | 1.6% |
| 2024 | 1,191,814 | 72.2% | 17.3% | 10.4% | 0.1% | 29.5% | 0.0% | 0.0% | 1.5% |
| 2025 | 1,161,132 | 71.6% | 19.7% | 8.6% | 0.1% | 28.4% | 0.0% | 0.0% | 1.1% |
| 2026 | 732,808 | 77.0% | 20.2% | 2.5% | 0.2% | 32.1% | 0.0% | 0.0% | 0.2% |

## Monitor de qualidade (v2)

A página `/qualidade` e o endpoint `GET /v1/qualidade` leem tabelas geradas pelo pipeline (`python -m sinalbr_data quality`); nada é recalculado a cada consulta.

| Tabela gold | Conteúdo | Definição |
|---|---|---|
| `qualidade_ano` | Indicadores por arquivo anual | % sobre os registros do arquivo; `fora_da_janela` = fatos fora de 2022..`dados_ate`; `tamanho_mb`/`fonte_modificada` nulos = manifesto indisponível (não zero) |
| `qualidade_categoria` | Por arquivo × tipo de crime | Cobertura do mapa (`coord_valida_pct`), sem hora, data imputada |
| `qualidade_semana` | Últimas 30 semanas | `completa` ≥ 85% da mediana das 8 anteriores; `parcial` ≥ 10%; `residual` < 10% |
| `qualidade_etapas` | Funil do pipeline | bronze → silver → gold por município → gold do mapa → gold da grade de horários |
| `execucoes` | Histórico de execuções | Acrescentado a cada `quality` em `lake/reports/runs.jsonl` |

**`dados_ate`** é o fim da última semana com volume não residual. Antes da v2 era o fim da última semana existente, e uma semana com 995 registros (5% do típico) fazia o painel dizer "dados até 06/09/2026".

### Achados (arquivos de 10/2026)

- **`DESCR_TIPOLOCAL` ausente em 2022, 2023 e 2024** (100%), não só em 2022: é mudança de layout da SSP.
- **A cobertura do mapa varia muito por tipo** (arquivo 2026): trânsito 92%, roubo 85%, furto 82%, lesão corporal 47%, crimes sexuais 0% (local ocultado pela fonte). O painel avisa quando a cobertura do tipo escolhido fica abaixo de 60%.
- **Furto não tem hora em ~43–45% dos registros**: a grade dia × hora de furto representa pouco mais da metade dos casos.
- **Funil:** 5.525.638 linhas lidas → 5.490.288 com fato na janela (99,4%) → 3.968.876 no mapa (71,8%) → 3.827.085 com hora (69,3%).
