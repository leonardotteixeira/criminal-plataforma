# Privacidade e LGPD

O SinalBR foi desenhado para **não tratar dados pessoais**. Este documento descreve as decisões técnicas e os limites. Não é parecer jurídico.

## O que usamos

Somente dados abertos publicados oficialmente:

- **SSP-SP / SPDados**: ocorrências registradas (arquivos anuais de transparência).
- **IBGE**: malha municipal e população do Censo 2022.

## Minimização na ingestão

O arquivo da SSP-SP traz campos que podem apontar para um local ou boletim específico. A ingestão (`data/src/sinalbr_data/bronze.py`) **descarta** logo na leitura:

| Campo original | Tratamento |
|---|---|
| `LOGRADOURO`, `NUMERO_LOGRADOURO` | Descartados; nunca gravados em disco |
| `NUM_BO` | Descartado |
| `LATITUDE`, `LONGITUDE` | Usadas só para validar e calcular o hexágono H3; **não persistidas** na camada silver |
| `NOME_DELEGACIA`, `ANO_BO`, `RUBRICA` | Mantidos apenas na bronze local, não expostos |

A SSP-SP já oculta o endereço de crimes sexuais (coordenadas `0.0`, "VEDAÇÃO DA DIVULGAÇÃO"); respeitamos isso e não tentamos recuperar o local por outros campos.

Um teste automatizado (`data/tests/test_pipeline.py`) falha se a silver contiver colunas de coordenadas ou endereço.

## Agregação e supressão

- Resolução espacial mínima: hexágono H3 nível 8 (~0,7 km²), bairro, município.
- Resolução temporal mínima: mês (semana apenas para séries agregadas por município).
- **Limite mínimo (k = 5)**: qualquer célula, município ou ponto de série com menos de 5 ocorrências no filtro escolhido não é exibido (`SINALBR_K_MIN`).
- A API só lê as tabelas **gold** (agregados). Não existe endpoint que devolva registros individuais.

### Ataque de diferenciação: evidência e controle (v2)

**Problema comprovado.** Com o k = 5 aplicado só ao total do filtro, subtrair duas janelas válidas revelava contagens pequenas. Usando apenas as janelas que o próprio painel oferece (12 meses menos 6 meses), **273 hexágonos de roubo** revelavam uma contagem de 1 a 4 registros num semestre (consulta no `cell_month`, out/2026). Pela API, que aceita qualquer intervalo, a diferença podia isolar um único mês.

**Controle implementado.** Toda contagem por hexágono (mapa e `/v1/export/celulas.csv`) é **arredondada para o múltiplo de 5 mais próximo**, com mínimo de 5 (`SINALBR_CELL_ROUND`). A ordem é esta:

1. o teste k-mínimo é aplicado sobre o valor exato;
2. só então o valor publicado é arredondado.

A diferença entre duas janelas passa a ter incerteza de ±5. Por exemplo, 12 e 9 viram 10 e 10 (teste `test_cell_rounding_hides_small_differences_between_windows`). O total do mapa aparece como aproximado (≈).

**Risco residual, documentado e não eliminado:**

- O arredondamento determinístico ainda vaza informação quando muitas janelas são combinadas, por exemplo, por limites de arredondamento. A proteção formal seria ruído diferencialmente privado (ex.: geométrico) com orçamento por consulta, o que exige controle de sessões e quebra a reprodutibilidade dos números. Fica para um uso público em produção.
- **Contagens municipais** (ranking, séries, comparador, Radar, relatórios) são publicadas exatas acima de k. A própria SSP publica estatísticas municipais mensais, e os microdados da fonte são públicos com endereço. O objetivo aqui é **não facilitar** o mapeamento fino de eventos, não proteger mais do que a fonte.
- Anomalias por hexágono H3 resolução 7 (~5 km², `nivel=h3_7`) expõem contagens semanais exatas, só a partir de 10 registros.
- Hexágonos com pouca população residente (áreas industriais, rodovias) podem concentrar ocorrências de um mesmo evento. Interprete com cuidado.
- A tabela `bairro_month` existe no lake, mas **não é exposta pela API**.

### Análises salvas

A função "Salvar visão" grava filtros e URLs só no `localStorage` do navegador. Não há conta, cookie de rastreamento nem envio a servidor.

## Bases legais e princípios (LGPD)

- Os dados de origem são públicos e agregados antes de qualquer exibição; o produto não identifica nem permite identificar pessoas.
- Princípios aplicados: finalidade, necessidade (minimização), adequação, segurança e prevenção (art. 6º).
- Dados anonimizados não são dados pessoais quando não é possível reverter a anonimização por meios razoáveis (art. 12). Tratamos a anonimização como **objetivo de projeto e risco residual**, não como garantia absoluta.

## O que o produto NÃO faz

- Não identifica, rastreia ou perfila indivíduos.
- Não recebe nem armazena dados de usuários além de preferências locais (tema) no navegador.
- Não deve ser usado para decisões sobre pessoas.

## Limitações de interpretação

- BOs refletem **registro**, não o crime real. A subnotificação varia por tipo de crime, bairro e perfil da vítima.
- Áreas com mais policiamento tendem a registrar mais; modelos treinados nesses dados podem **reforçar vieses de policiamento**.
- Os meses mais recentes são parciais por atraso de registro.

## Revisão v3 (2026-10-11): auditoria de endpoints e controles adicionais

### Vazamentos encontrados e corrigidos (medidos no lake real)

| Vazamento | Mecanismo | Antes | Depois | Controle |
|---|---|---:|---:|---|
| Comparador | total do município − categorias exibidas = categoria suprimida | 70 de 645 municípios com contagem exata revelada | 0 | Agregação consistente |
| Ranking "todos os crimes" | total − soma dos 8 rankings por categoria | 13 (nos 100 primeiros) | 0 | Agregação consistente |
| Tendência municipal | pontos mensais de 1 a 4 publicados | presentes (ex.: 2/mês) | 0 | Supressão de pontos |
| `/v1/series` | suprimido devolvido como `0` | 100% dos pontos suprimidos | nulo + `suprimido` | Semântica explícita |
| Hexágonos | janela arbitrária isolava um mês por diferença | aceito | HTTP 422 | Janelas ancoradas |

### Controles (código em `api/app/protecao.py`)

1. **k-mínimo (5)** em toda contagem publicada.
2. **Agregação consistente:** qualquer total "todos os crimes" (mapa, ranking, CSV, séries, comparador, decomposição) é a soma das categorias que seriam publicadas isoladamente no mesmo recorte. Assim, "total − categorias exibidas" é sempre 0.
3. **Supressão de pontos com estatísticas derivadas protegidas:**
   - meses abaixo de k numa série municipal ficam nulos;
   - variação de 12 meses, inclinação e sazonalidade só são calculadas se nenhum ponto da janela foi suprimido. Do contrário, combinadas aos pontos publicados, permitiriam recalcular o valor oculto.
4. **Hexágonos:**
   - janelas ancoradas de 3, 6, 12 ou 24 meses terminando na data dos dados;
   - contagens arredondadas para múltiplos de 5.

   A diferença entre duas janelas publicadas só delimita o valor real num intervalo de largura ≥ 5 (ex.: [0, 4] ou [1, 9]); nunca revela uma contagem exata.
5. **Textos do radar** nunca escrevem contagens abaixo de k ("menos de 5").
6. **Mapa e exportação** usam a mesma função (`_heatmap`): o CSV não tem informação a mais que o mapa.

### O que continua sem garantia formal

- **Diferença entre janelas no nível municipal.** Em `/v1/comparacao/periodos` (janelas livres) e no perfil (6/12/24 meses), a diferença entre janelas ainda pode revelar a soma de meses com poucos registros num município pequeno. Mantido por utilidade e porque a SSP já publica estatísticas mensais por município.
- **Inferência por limites.** Uma diferença publicada 0 entre janelas de hexágono indica que o bloco teve entre 0 e 4 registros. É informação de limite superior, não um valor exato.
- **Ataques com conhecimento externo** (alguém que conhece um evento específico) não são cobertos por k-anonimato nem por arredondamento.

### Desenho recomendado se o produto for público (não implementado)

- **Modelo de ameaça:** um usuário com acesso ilimitado à API tenta inferir, por combinação de consultas, a contagem de um hexágono × mês × categoria, ou a presença de um evento específico.
- **Consultas protegidas:** apenas um conjunto **fixo e pré-calculado** de liberações (hexágono × janela ancorada × categoria). A API deixaria de calcular agregados sob demanda.
- **Mecanismo:** ruído geométrico (Laplace discreto) com sensibilidade 1 por evento, aplicado uma vez na geração. As liberações ficam congeladas, então repetir a consulta não reduz o ruído.
- **Composição do orçamento:** cada evento entra em até 4 janelas × 2 agregações (categoria e total consistente). Com ε por liberação, o orçamento por atualização é ε_total = 8ε (composição sequencial); entre atualizações, as janelas se sobrepõem e o orçamento se acumula.
- **Validação:**
  - erro relativo das células com ≥ 30 registros < 10%;
  - estabilidade dos rankings (correlação de Spearman com o dado exato);
  - impacto nas análises (radar e previsão recalculados sobre os dados ruidosos);
  - teste empírico de ataque de diferenciação nas liberações.
- **Por que não agora:**
  - exige liberar só tabelas pré-calculadas (perde a consulta flexível);
  - a previsão e o radar precisariam usar os mesmos dados ruidosos;
  - escolher ε exige uma decisão de política, não só técnica.
