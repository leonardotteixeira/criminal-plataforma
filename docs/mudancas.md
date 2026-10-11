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

---

## Avaliação v3 (2026-10-11): sazonalidade municipal, múltiplas comparações e histórico

Reproduzir: `cd data && uv run python -m sinalbr_data changes` (sementes fixas). Resultados em `gold/mudancas_comparacao.parquet`, `mudancas_simulacao.parquet`, `mudancas_fdr.parquet`, `mudancas_estabilidade.parquet`; visíveis em `/qualidade#mudancas`.

### Motivação

A participação do município no total estadual tem sazonalidade própria. Considerando as séries com ≥ 40 registros/mês, a razão pico/média mensal vale 1,13 na mediana, 1,30 no p90 e 2,9 no p99. Exemplos: Barretos/furto 2,8× em agosto (Festa do Peão); Campos do Jordão/furto 1,9× em julho. O modelo v1 assume a sazonalidade do estado.

### Alternativa avaliada: modelo sazonal

`μ_t = p · S_t · f_t`, onde `f_t` é a razão entre a participação do município na janela de 5 semanas do ano anterior e a participação na linha de base equivalente do ano anterior. O fator é encolhido para 1 conforme o volume: `w = n/(n+λ)`, com λ = 20.

### Desenho da comparação (equivalente entre métodos)

- **Mesmo conjunto de séries e origens para todos os métodos.** Origens a cada 4 semanas desde que existam 1 ano + 38 semanas de histórico e 8 semanas futuras: 24.571 avaliações (série × origem) em 2023–2026.
- **Duas verdades fora da amostra** (8 semanas seguintes):
  - **T1:** o patamar continuou ≥ 1,1× (ou ≤ 0,9×) o esperado pelo padrão estadual;
  - **T2:** idem, descontando também a sazonalidade do ano anterior. T2 usa o mesmo estimador do modelo sazonal e, por isso, o favorece por construção.
- **Ganho** = confirmação ÷ confirmação por acaso. O acaso é a fração de **todas** as séries com razão futura na mesma faixa, ponderada pelas direções dos sinais.

### Resultados principais (H = 5)

| Método | Sinais | Confirma T1 | Ganho T1 | Confirma T2 | Ganho T2 |
|---|---:|---:|---:|---:|---:|
| Referência simples | 2.201 | 68,7% | 2,28× | 62,0% | 1,89× |
| Participação (v1) | 1.935 | 68,3% | 2,33× | 63,6% | 2,00× |
| **Participação + BH (adotado)** | 1.766 | 69,2% | **2,37×** | 64,0% | 2,02× |
| Sazonal | 3.138 | 57,2% | 1,89× | 70,1% | 2,14× |

Ganho T1 por tipo (entre parênteses, número de sinais):

| Tipo | Referência | Participação | Participação + BH | Sazonal |
|---|---|---|---|---|
| Roubo | 2,12× (266) | 2,23× (244) | 2,23× (239) | 1,77× (468) |
| Furto | 2,32× (858) | 2,31× (810) | 2,31× (797) | 1,92× (1.295) |
| Lesão corporal | 2,17× (378) | 2,38× (248) | 2,50× (159) | 1,85× (425) |
| Drogas | 2,16× (466) | 2,17× (404) | 2,16× (389) | 1,82× (528) |
| Trânsito | 2,22× (224) | 2,38× (220) | 2,50× (173) | 1,89× (394) |
| Sexual / homicídio / armas | poucos sinais (≤ 20): sem conclusão | | | |

**Outros recortes:**
- **Faixa de volume:** a participação vence a sazonal nas três faixas (3–10, 10–30, ≥ 30 registros/semana).
- **Ano:** a participação + BH tem ganho ≥ a participação em 2023, 2024, 2025 e 2026.
- **Sensibilidade a λ:** com λ = 100 o sazonal sobe para 2,13× (T1) e, com λ = 400, para 2,28×. Ou seja, converge para o modelo de participação e nunca o supera.
- **Sensibilidade a H** (participação): H = 4, 5 e 6 dão 2.888, 1.935 e 1.336 sinais, com ganho 2,22×, 2,33× e 2,42×. Mantivemos H = 5, definido antes da avaliação, para não ajustar o método aos mesmos dados usados para avaliá-lo.

**Simulação** (forma real da série estadual; 300 réplicas; falso alarme sem mudança real):

| Registros/semana | Sazonalidade municipal | Referência | Participação | Sazonal |
|---:|---|---:|---:|---:|
| 10 | não | 6,7% | 3,7% | 8,7% |
| 10 | sim | 7,3% | 5,3% | 4,3% |
| 30 | não | 2,7% | 3,7% | 7,3% |
| 30 | sim | 9,7% | 7,0% | 4,7% |

O modelo sazonal ajuda quando a sazonalidade municipal existe. Quando ela não existe, o fator estimado com um único ano adiciona ruído. Nos dados reais o efeito líquido é negativo.

**Decisão:** manter o modelo de participação; o sazonal fica só no código de avaliação (`metodo="sazonal"`), para reprodutibilidade. Melhorar a estimativa (vários anos, pooling entre municípios) só faz sentido com mais histórico.

### Múltiplas comparações

- **Hipótese nula, por série:** sem mudança, os resíduos padronizados `z_t` nas 12 semanas monitoradas são i.i.d. N(0,1).
- **Estatística:** máximo bilateral do CUSUM.
- **p-valor:** P(máximo nulo ≥ observado), com tabela de 100 mil sequências simuladas (semente fixa).
- **Calibração** (teste `test_p_value_is_roughly_calibrated_under_the_null`): sob o nulo de Poisson, P(p < 0,05) fica entre 1% e 10%.
- **Procedimento:** Benjamini–Hochberg com q = 0,10 sobre todas as séries elegíveis de cada atualização (~700 por categoria).

**Resultado:**
- **Nos dados reais**, o BH remove ~9% dos sinais e aumenta o ganho de forma pequena e consistente (2,33× → 2,37×; maior em todas as faixas e anos).
- **Nos lotes simulados** (10% de mudanças reais e sazonalidade municipal), a proporção de falsas descobertas fica em 42–47% **com ou sem BH**. Os falsos alarmes vêm de desvios do modelo (sazonalidade não modelada), que também geram p-valores pequenos.

**O BH controla a FDR só se o nulo estiver correto; aqui ele é aproximado.** Por isso o radar diz que ~1 em cada 3 sinais não se confirma, e não promete uma FDR de 10%.

### Estabilidade temporal

Só 41% dos sinais da participação reaparecem (mesma direção) na avaliação seguinte, 4 semanas depois; a referência fica em 44%. Isso motivou o histórico abaixo.

## Histórico do Radar (`data/src/sinalbr_data/history.py`)

**Por que não bastavam as tabelas atuais:** `gold/mudancas` guarda só a origem atual, e as anomalias guardavam só 26 semanas (agora 56). Sem snapshots não há como saber se um sinal é novo ou se já existia.

**Esquema mínimo:**
- `lake/history/radar_snapshots.parquet`: observações detectadas, com `versao_dados`, `semana_completa_ate`, `metodo`, `modo`, `origem`, `obs_id`, métricas e `gerado_em`.
- `lake/history/radar_avaliadas.parquet`: séries avaliáveis por origem. É o que separa "não detectado" de "não avaliado".
- `gold/radar_historico.parquet`: resumo por observação, lido pela API.

**Identificador estável:** `tipo|categoria|cd_ibge|direção`. A data de início estimada não entra, porque oscila entre origens. Inverter a direção cria outra observação, e ela fica marcada com `mudou_direcao`.

**Idempotência:** o bloco (versão dos dados, semana de referência, método) é substituído a cada execução. Outros blocos são preservados, então atualizações reais da SSP acumulam histórico. Testes impedem duplicações.

**Modos:**
- `reconstrucao`: 13 origens passadas recalculadas com os dados e o método atuais. **Não** é o que foi exibido na época, porque a fonte revisa dados.
- `atualizacao`: a origem atual de cada versão.

**Estados (mudanças persistentes):**
- `novo`, `persistente`, `historico_insuficiente`;
- `deixou_de_ser_detectado`: o critério deixou de ser atendido, o que **não** significa que a situação foi resolvida;
- `sem_avaliacao_atual`.

Picos semanais recebem `novo`, `recorrente` ou `anterior`, sem estado de encerramento, porque são eventos pontuais.

**Na referência de 23/08/2026:** 55 mudanças, sendo 29 persistentes, 22 novas e 4 com histórico insuficiente; outras 30 deixaram de ser detectadas.
