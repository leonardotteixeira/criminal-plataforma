# Mudanças persistentes e Radar territorial

Código: `data/src/sinalbr_data/changes.py` (detecção e avaliação), `api/app/radar.py` (seleção e textos). Testes: `data/tests/test_changes.py`, `api/tests/test_v2.py`.

## Pergunta

"O município passou a registrar, **de forma sustentada**, mais (ou menos) ocorrências do que o padrão estadual explicaria?" O detector não responde **por quê**: a causa pode ser real, de registro (lote de BOs, mudança de delegacia de referência) ou de policiamento.

## Por que não usar só a série do próprio município

O roubo caiu ~20% em todo o estado em 12 meses. Um detector que compara o município com o próprio passado sinaliza quedas em quase todo lugar, o que é verdadeiro, mas não diz nada **local**. O **modelo de participação** usa como esperado `μ_t = p · S_t`, onde `S_t` é o total estadual do crime na semana e `p` é a participação do município nas 26 semanas de linha de base. Sazonalidade estadual, feriados, atraso de registro e tendência estadual saem automaticamente do esperado (teste `test_statewide_trend_is_not_a_local_change_but_fools_the_naive_reference`).

## Método escolhido: CUSUM bilateral

Entre CUSUM, EWMA e PELT, escolhemos o CUSUM:

- tem regra de parada explícita;
- estima o início da mudança (último zero antes do alarme);
- é barato, com mais de 40 mil séries avaliadas em segundos;
- é fácil de auditar.

O PELT exigiria escolher penalidades e se volta à segmentação retrospectiva, não ao monitoramento.

O cálculo usa:

- resíduo `z_t = (x_t − μ_t)/√(φ μ_t)`, com superdispersão `φ` estimada na linha de base (mínimo 1);
- parâmetros K = 0,5 e H = 5, sobre as 12 semanas monitoradas.

Um sinal só é "persistente" se cumprir as três condições:

- ≥ 4 semanas desde o início estimado;
- magnitude ≥ 20%;
- as 4 últimas semanas na mesma direção (≥ 10%).

Picos isolados de uma semana não passam (teste `test_isolated_spike_is_not_persistent`).

Só são avaliadas séries com média esperada ≥ 3 registros/semana.

A **referência simples** compara a razão das últimas 8 semanas com a média das 26 de linha de base (|razão−1| ≥ 25% e z de Poisson ≥ 3), sem ajuste estadual.

## Avaliação

### Simulação (série estadual real de roubo como forma; ruído binomial negativo φ = 1,5; 400 réplicas)

| Registros/semana | Cenário | CUSUM | Referência | Atraso CUSUM |
|---:|---|---:|---:|---:|
| 3 | sem mudança (falso alarme) | 0,8% | 2,0% | — |
| 3 | alta de 50% | 10,3% | 5,8% | 5,2 sem. |
| 10 | sem mudança | 3,8% | 4,0% | — |
| 10 | alta de 30% | 36,3% | 27,5% | 4,5 sem. |
| 30 | sem mudança | 1,3% | 2,8% | — |
| 30 | alta de 30% | 72,0% | 42,8% | 4,2 sem. |
| 30 | queda de 30% | 80,3% | 84,3% | 4,6 sem. |

O falso alarme fica entre 1% e 4% por janela de 12 semanas. O poder depende muito do volume: com cerca de 3 registros/semana o detector quase nunca encontra mudanças, mesmo reais. **Ausência de sinal não é evidência de estabilidade.**

### Retrospectiva nos dados reais (origens a cada 4 semanas, 2023–2026)

**Confirmado** significa que, nas 8 semanas **seguintes** ao fim da janela (fora da amostra), a razão observado/esperado continuou ≥ 1,1 (alta) ou ≤ 0,9 (queda). **Por acaso** é a mesma taxa medida em todas as séries avaliadas, ponderada pelas direções dos sinais.

| Tipo | Séries | Sinais | Confirmados | Por acaso | Referência (acaso) | No Radar |
|---|---:|---:|---:|---:|---:|---|
| Roubo | 3.875 | 370 | 67,8% | 30,0% | 76,5% (40,2%) | sim |
| Furto | 12.297 | 1.136 | 65,8% | 29,1% | 70,5% (31,9%) | sim |
| Lesão corporal | 7.759 | 323 | 64,7% | 25,9% | 69,7% (34,2%) | sim |
| Drogas | 4.571 | 554 | 75,3% | 35,3% | 79,6% (38,0%) | sim |
| Trânsito | 4.725 | 289 | 72,3% | 28,8% | 68,3% (31,9%) | sim |
| Crimes sexuais | 460 | 13 | 61,5% | 28,8% | 54,5% (30,3%) | não (poucos sinais) |
| Homicídio | 100 | 2 | 0% | 17,0% | 62,5% (28,0%) | não |
| Porte de arma | 48 | 0 | — | — | — | não |

### Leitura honesta

- **Os sinais carregam informação.** A confirmação fica entre 2,2 e 2,5 vezes a taxa do acaso.
- **A referência simples confirma em proporção parecida**, mas sobre uma taxa base mais alta: o ganho relativo do CUSUM é modesto.
- **O valor do CUSUM está em outro lugar:**
  - estima o início e a magnitude da mudança;
  - tem mais poder para altas moderadas (simulação);
  - desconta movimentos do estado inteiro.
- **Portão de confiabilidade.** O Radar só mostra mudanças de tipos com ≥ 50 sinais históricos avaliados e confirmação ≥ 1,5 vez a taxa do acaso.

### Limitações

- A sazonalidade própria de um município (litoral no verão) não é modelada; o modelo assume a sazonalidade do estado.
- Não há correção de multiplicidade: com milhares de séries, alguns sinais são falsos positivos.
- As origens retrospectivas se sobrepõem, então não são independentes.
- Mudanças de prática de registro e de delegacia de referência são indistinguíveis de mudanças reais.

## Radar territorial (`GET /v1/radar`)

O Radar aplica regras determinísticas, sem modelo de linguagem. Cada item traz o tipo, o período, a região, as métricas e a explicação; os critérios voltam na própria resposta (`criterios`).

| Tipo | Critério |
|---|---|
| `mudanca_persistente` | Saída do CUSUM acima, só para os tipos aprovados no portão de confiabilidade. Quando o início coincide com a 1ª semana monitorada, o texto diz "desde pelo menos". |
| `variacao` | 12 meses completos contra os 12 anteriores, com ≥ 200 registros no período anterior; a razão do município sobre a razão do estado difere de 1 em ≥ 25% e \|z\| ≥ 4 (aproximação de Poisson, usada como triagem). |
| `anomalia` | Picos semanais (`gold/anomalias`) nas últimas 4 semanas completas; "recorrente" se sinalizados em ≥ 3 das últimas 8. |
| `dados` | Semanas recentes incompletas e cobertura do mapa < 60% para o tipo filtrado. |

Uma lista vazia mostra um texto explicando o que a ausência **não** significa.
