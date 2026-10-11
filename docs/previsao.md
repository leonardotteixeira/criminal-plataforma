# Previsão de risco (Fase 3)

## O que é previsto
Registros de BO nas **próximas 4 semanas** por hexágono H3 **res. 7 (~5 km²)**, para roubo, furto e lesão corporal dolosa. Só entram células com ao menos 60 registros em 104 semanas (2.746 células); crimes raros (homicídio, sexuais, armas) ficam de fora porque a contagem por célula é pequena demais para um modelo honesto.
O alvo é **registro**, não crime real, e a previsão herda o viés de policiamento/registro (ver abaixo).

## Modelos comparados
| Modelo | Descrição |
|---|---|
| persistência | contagem das últimas 4 semanas |
| média12 | média semanal das últimas 12 semanas × 4 (**baseline principal**) |
| sazonal | mesmas 4 semanas do ano anterior |
| glm | regressão de Poisson (IRLS + ridge) com log das somas de 4/12/26/52 semanas, ano anterior e sazonalidade (sen/cos) |
| glm_viz | glm + soma de 12 semanas das 6 células vizinhas (anel 1) |
| oráculo | usa o próprio alvo para ranquear: **teto** da métrica de captura |

## Protocolo de backtest (sem vazamento)
Origem móvel nas últimas 24 semanas completas (24 origens); refit a cada 4 semanas usando **apenas origens cujo alvo já havia terminado**. Um teste unitário (`tests/test_forecast.py::test_backtest_has_no_future_leakage`) verifica que o modelo não "enxerga" uma mudança de regime que só ocorre no período de teste.
Métricas: desvio de Poisson (menor é melhor), MAE e **captura top-10%** (fração dos eventos reais que caem nas 10% células de maior previsão, por origem).

## Resultados (dados reais, origem 2026-08-17)
| Crime | Desvio baseline→modelo | Redução | Captura média12 → modelo | Teto | Modelo > baseline em |
|---|---|---:|---|---:|---:|
| roubo | 2,163 → 1,855 | 14,2% | 38,85% → 38,93% | 40,2% | 58% das origens |
| furto | 2,823 → 2,398 | 15,0% | 54,80% → 55,08% | 55,8% | 100% |
| lesão corporal | 1,632 → 1,341 | 17,9% | 23,41% → 23,86% | 27,0% | 75% |

### Leitura honesta
- O modelo **melhora a contagem esperada** (desvio −14% a −18%) de forma consistente.
- Para **ranquear onde** há mais ocorrências, o ganho é pequeno (+0,1 a +0,5 p.p.) e já próximo do teto: os pontos quentes são muito persistentes, uma média móvel simples os encontra. Não prometemos que o modelo "descobre" áreas que um mapa de calor histórico não mostra.
- Calibração: nos decis de previsão, o observado ficou ~3–10% acima do previsto no período de teste (leve subestimação, p.ex. roubo no 10º decil: 61,9 previsto vs 65,1 observado).
- A vizinhança ajuda muito pouco (desvio 1,869 → 1,855 em roubo).
- 24 origens consecutivas são correlacionadas (alvos de 4 semanas se sobrepõem) e há só 6 refits; as diferenças pequenas de captura **não devem ser lidas como significativas**.

## Viés e uso responsável
- Mais policiamento → mais registro → mais "risco" previsto → mais policiamento (feedback loop). A previsão não distingue ocorrência de registro.
- Subnotificação varia entre crimes e regiões; áreas com menor confiança nas instituições registram menos.
- A faixa (alta/média/baixa) é **relativa** dentro do tipo de crime, não um nível absoluto de perigo.
- Não é uma ferramenta para decisões sobre pessoas ou para justificar abordagens. Uso indicado: apoio a planejamento territorial e a discussão pública, junto de outras fontes.

## Limitações técnicas
Sem intervalos de previsão (superdispersão não modelada); vizinhança só entre células do painel; sem eventos/feriados; população não entra como variável; janela de teste curta (6 meses).
