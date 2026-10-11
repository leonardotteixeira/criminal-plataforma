# Auditoria v2 e priorização (2026-10-11)

Auditoria feita lendo o código e consultando o lake real (não só o README). "Comprovado" = há evidência reproduzível; "hipótese" = precisa de verificação.

## Matriz de achados

| # | Área | Estado atual | Problema | Evidência | Severidade | Melhoria | Esforço |
|---|---|---|---|---|---|---|---|
| 1 | Privacidade | k = 5 aplicado ao total do filtro | **Diferenciação entre janelas** fura o k: subtraindo a janela de 6 meses da de 12 meses (ambas oferecidas pelo painel), 273 hexágonos de roubo revelam contagens entre 1 e 4 num semestre | Consulta no `cell_month` (comprovado) | Crítico | Arredondar contagens de hexágono para múltiplos de 5 na API e nas exportações; documentar risco residual | Baixo |
| 2 | Dados/API | `dados_ate` = fim da última semana existente | Uma semana residual (995 registros vs ~18 mil) e 1 registro em set/2026 fazem o painel dizer "dados até 06/09/2026" | `mun_week`, `cell_month` (comprovado) | Alto | Definir `dados_ate` no pipeline ignorando semanas residuais (< 10% da mediana) | Baixo |
| 3 | UX | Município só pelo top-10 do ranking | Impossível analisar 635 dos 645 municípios no painel | `dashboard/page.tsx` (comprovado) | Alto | Seletor pesquisável de município, sincronizado com a URL | Médio |
| 4 | UX | URL só define estado inicial | Link copiado depois de mudar filtros não reproduz a visão | `dashboard/page.tsx` (comprovado) | Médio | Sincronizar filtros com a URL | Baixo |
| 5 | Produto | `/v1/comparacao/regioes` sem tela | Comparação regional existe só na API | `grep` no web (comprovado) | Alto | Página de comparação | Médio |
| 6 | Analytics | Só anomalias pontuais (pico de 1 semana) | Não distingue pico isolado de mudança persistente; queda estadual de −20% faz quase todo município "cair" | `analytics.py` (comprovado) | Alto | Detector de mudança persistente relativo ao padrão estadual, com avaliação retrospectiva | Médio |
| 7 | Produto | Alertas = lista de anomalias | Falta uma porta de entrada que diga o que mudou e por quê | — | Alto | Radar com critérios explícitos | Médio |
| 8 | Dados | Qualidade só em Markdown estático | Usuário não vê confiabilidade por ano/categoria/semana; sem histórico de execuções | `quality.py` (comprovado) | Médio | Tabelas de qualidade + histórico de execuções + página | Médio |
| 9 | Relatório | Só estado, sem distribuição de categorias, anomalias, qualidade ou versão dos dados | — | `relatorio/page.tsx` (comprovado) | Médio | Relatório estruturado por região | Médio |
| 10 | Marca | `/v1/meta` fixa "SinalBR" | Fora da centralização | `api/app/main.py` (comprovado) | Baixo | Variável `SINALBR_BRAND` | Baixo |
| 11 | UI | Erros mostram texto cru ("Failed to fetch"); estilos de cards/avisos repetidos inline | Mensagens pouco úteis; inconsistência | componentes (comprovado) | Médio | Componentes de estado e aviso compartilhados | Médio |
| 12 | Gráficos | Linha sem eixos com unidade, sem leitura de valor | Difícil interpretar escala | `Charts.tsx` (comprovado) | Médio | Eixo com unidade, gradeado, valores por ponto (tooltip nativo), multi-série | Baixo |
| 13 | Analytics | Aba Alertas ignora o município selecionado | — | `dashboard/page.tsx` (comprovado) | Baixo | Filtro por município no endpoint de anomalias | Baixo |
| 14 | Dados | `bairro_month` (1,7 mi linhas) não é usado | Custo sem uso; bairro é granularidade sensível | `gold.py` (comprovado) | Baixo | Manter fora da API; documentar | — |
| 15 | Hipótese | Municípios com sazonalidade própria (litoral) | Podem gerar falsos alarmes no detector de mudanças | a verificar na avaliação retrospectiva | — | Medir e documentar | — |

## Priorização da rodada

| Entrega | Impacto | Diferenciação | Complexidade | Risco estatístico | Decisão |
|---|---|---|---|---|---|
| Correções 1, 2, 10 | Alto | — | Baixa | — | **Agora** |
| D. Mudanças persistentes | Alto | Alta | Média | Alto (mitigado por avaliação) | **Agora** (base do radar) |
| A. Radar territorial | Alto | Alta | Média | Médio | **Agora** |
| G. Seletor pesquisável + URL | Alto | Baixa | Baixa | — | **Agora** (pré-requisito da navegação do radar) |
| B. Comparador de regiões | Alto | Média | Média | Médio | **Agora** |
| F. Monitor de qualidade | Médio | Alta | Média | Baixo | **Agora** |
| E. Relatório estruturado | Médio | Média | Média | Baixo | **Agora** |
| Polimento visual (11, 12) | Médio | — | Média | — | **Agora**, junto das telas acima |
| H. Análises salvas (local) | Médio | Baixa | Baixa | — | Agora, se couber |
| I. Histórico de anomalias | Médio | Média | Baixa | — | Parcial: persistência derivada da tabela atual, dentro do radar |
| C. Sazonalidade | Baixo | Baixa | Baixa | — | Parcial: comparação entre anos no gráfico |
| J. Laboratório de hipóteses | Médio | Alta | Alta | Alto | **Adiado**: o radar + comparador já respondem às perguntas-exemplo de forma guiada |
| K. Alertas configuráveis | Baixo | Baixa | Média | — | **Adiado**: sem infraestrutura de notificação, seriam análises salvas |
| L. Assistente com IA | Baixo | Média | Alta | Alto | **Não agora**: exige credenciais/custo e não acrescenta análise verificável nova |

## Resultado da rodada

| # | Situação |
|---|---|
| 1 | Feito: arredondamento por hexágono (API e CSV), teste e documentação do risco residual |
| 2 | Feito: `dados_ate` = fim da última semana não residual (agora 30/08/2026) |
| 3, 4 | Feito: seletor pesquisável (combobox acessível) e URL sincronizada no painel, radar e comparador |
| 5 | Feito: página `/comparar` + `GET /v1/comparacao/perfil` |
| 6 | Feito: `changes.py` (CUSUM relativo ao estado) com simulação e retrospectiva; ver mudancas.md |
| 7 | Feito: `/radar` + `GET /v1/radar` |
| 8 | Feito: tabelas de qualidade, histórico de execuções, `/qualidade` |
| 9 | Feito: relatório de 12 seções, estado ou município |
| 10 | Feito: `SINALBR_BRAND` |
| 11, 12 | Feito: `ui.tsx`, cores semânticas, gráfico multi-série com eixos/unidade/legenda |
| 13 | Feito: `cd_ibge` em `/v1/anomalias` e na aba Alertas |
| 15 | Medido: sem modelagem de sazonalidade municipal; documentado como limitação |
