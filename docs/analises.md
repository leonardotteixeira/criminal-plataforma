# Análises (Fase 2): métodos, validação e limites

## Janela de completude
O registro de BOs tem atraso. Definimos `semana_completa_ate` como a última semana cujo total estadual é ≥ 85% da mediana das 8 semanas anteriores (hoje: semana de 2026-08-17). Tendências, comparações e anomalias usam **só meses/semanas completos**; o mapa e a série mensal simples mostram o mês parcial sinalizado.

## Padrões temporais (`/v1/tendencia`, `/v1/hora-dia`)
- Série mensal, variação dos últimos 12 meses vs. 12 anteriores e inclinação linear (regressão simples sobre 24 meses, em % da média por ano).
- Sazonalidade: média do índice (mês ÷ média do ano) nos anos completos (2022–2025).
- Dia da semana × hora: ~30% dos BOs não informam hora; o padrão vale só para os que informam.

## Comparações (`/v1/comparacao/*`)
- Entre períodos (estado ou município) e ranking de maiores altas/quedas com base mínima configurável.
- Entre regiões: **taxa por 100 mil hab.** (Censo 2022) e série mensal da taxa. Limitação: população fixa em 2022 (não projetada); municípios pequenos oscilam muito.
- Valores abaixo de k = 5 são suprimidos.

## Anomalias (`/v1/anomalias`, pipeline `analytics.py`)
Para cada município (e hexágono H3 res. 7, ~5 km²) × crime, compara a contagem semanal com a **mediana das 12 semanas anteriores**. Escala = max(1,4826·MAD, √mediana) (piso de ruído de Poisson). Sinaliza z ≥ 3, razão ≥ 1,3 e n ≥ 10, nas últimas 26 semanas completas.

**Verificação com dados reais** (580 sinais em 26 semanas: 210 município, 370 H3-7). Os maiores picos que investiguei tinham explicação externa plausível: Morumbi (SP) em semanas de grandes eventos (furtos 218 vs ~7 esperados), Caçapava (picos de dois dias) e Barretos em agosto (compatível com a Festa do Peão). Isso é **correto para o detector** (há mesmo concentração de registros), mas não é "onda de crime": eventos de massa e lotes de registro geram picos. A interface avisa isso.

Limitações: sem sazonalidade anual nem calendário de feriados/eventos; sem correção de multiplicidade (muitas séries testadas, alguns falsos positivos são esperados); a série semanal de cada município pequeno é ruidosa.

## Achado a investigar
Itapecerica da Serra aparece com a maior taxa de roubo por 100 mil hab. (≈ 769) e com um pico de furtos (164 vs 26) em jul/2026. Pode refletir a rodovia/comércio local ou lote de registro; não foi investigado a fundo.

## Resultado agregado (roubo, estado de SP)
Últimos 12 meses completos vs. 12 anteriores: **−20,3%** em registros (163,3 mil vs. 204,9 mil). É variação de **registros**, e mudanças de prática de registro também a afetam.

## v2: comparador, radar e mudanças persistentes

- **Comparador** (`GET /v1/comparacao/perfil`, página `/comparar`): até 4 municípios, sempre nos últimos N meses **completos** (6, 12 ou 24) contra os N anteriores.
  - Mostra contagem e taxa por 100 mil hab. em colunas separadas, para não confundi-las, além da participação de cada tipo no total do município.
  - Calcula a **razão de taxas** de cada município em relação ao de referência, com IC 95% aproximado: Poisson alargado pela superdispersão das contagens mensais, √φ, com φ = var/média, um valor conservador.
  - Não corrige diferenças de subnotificação ou de prática de registro. Quando o intervalo inclui 1, o texto diz que a diferença não se distingue da variação aleatória.
- **Radar e mudanças persistentes:** método, critérios e avaliação em [mudancas.md](mudancas.md).
- **Comparação entre anos** (aba Tempo e relatório): um traço por ano no eixo jan–dez, usando só meses completos.

## v3: investigação (aba "Investigar" do painel)

- **Decomposição das variações** (`GET /v1/decomposicao`): quanto cada tipo de crime (ou, para o estado, cada município) somou à variação do total entre os últimos N meses completos e os N anteriores. É aritmética: a soma das contribuições é a variação do total. Só entram itens com ≥ 5 registros nos dois períodos; os totais são a soma desses itens (agregação consistente). No recorte por município, os restantes viram "demais municípios" (só com 2 ou mais). Exemplo real: no estado, a variação total de −5,7% veio de roubo (61,6% da variação) e furto (60,7%); lesão corporal (−17,0%) e drogas (−8,4%) foram na direção contrária.
- **Robustez da conclusão** (`GET /v1/robustez`): verifica se "aumentou/diminuiu" se sustenta:
  - janelas de 6, 12 e 24 meses;
  - mesmo trimestre do ano anterior (controla a sazonalidade);
  - intervalo de 95% da razão de 12 meses, com Poisson × superdispersão mensal;
  - comparação com o estado (pontos percentuais).

  Vereditos:
  - `consistente`;
  - `parcialmente_consistente`: nenhuma janela aponta a direção oposta, mas alguma fica estável (< 5%). Típico de mudança já ocorrida que se mantém;
  - `sensivel_a_janela`: a direção se inverte;
  - `indistinguivel_do_ruido`: o intervalo inclui 1;
  - `insuficiente`.

  Exemplos reais:
  - roubo no estado: consistente;
  - Sorocaba/drogas: parcialmente consistente (+113% em 12 meses, +2,6% em 6 meses);
  - Campinas/homicídio: indistinguível do ruído (+23% em 12 meses, IC inclui 1).

  O resultado inclui o que a cobertura dos dados (local e hora) permite concluir para o tipo.
- **Descartadas nesta rodada:**
  - municípios "semelhantes": exige definir e validar uma métrica de similaridade;
  - perguntas guiadas e chatbot: a aba Investigar + o radar já cobrem as perguntas-exemplo com operações verificáveis.
