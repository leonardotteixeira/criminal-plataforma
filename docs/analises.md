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
