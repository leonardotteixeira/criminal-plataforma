# Auditoria v3 e priorização (2026-10-11)

## Estado verificado antes de alterar

- Árvore Git limpa; último commit `2a6e92a`. Testes: data 31, api 26, web 28, todos passando.
- A API em execução na porta 8000 é a **versão antiga** (sem `/v1/radar`; `dados_ate` = 06/09/2026). O frontend na porta 3000 (`next dev`) já serve o código novo, então as telas novas falham até a API ser reiniciada. Não alterei esses processos.
- Docker continua indisponível no ambiente (`docker: command not found`).

## Achados novos (comprovados no lake real)

| # | Área | Problema | Evidência | Severidade |
|---|---|---|---|---|
| 1 | Privacidade | **Supressão complementar ausente no comparador.** O total do município menos as categorias exibidas revela a contagem exata de uma categoria suprimida | 70 de 645 municípios (ex.: Araçariguama, porte de arma = 4) | Crítico |
| 2 | Privacidade | O mesmo no ranking "todos os crimes": o total menos a soma das 8 categorias revela uma categoria suprimida | 13 dos 100 primeiros municípios | Crítico |
| 3 | Privacidade | `/v1/tendencia` com município expõe pontos mensais de 1 a 4 (só suprime se o total < 60) | Alumínio, roubo: 2/mês | Alto |
| 4 | Privacidade/API | `/v1/series` devolve suprimido como `n=0`, indistinguível de zero real | 5 de 5 pontos de homicídio num município pequeno | Médio |
| 5 | Estatística | O detector usa a sazonalidade **do estado**; a participação municipal tem sazonalidade própria | Pico/média da participação mensal: mediana 1,13, p90 1,30, p99 2,9 (Barretos/furto 2,8× em agosto; Campos do Jordão 1,9× em julho) | Alto |
| 6 | Estatística | Sem controle de múltiplas comparações (~2–3 mil séries por atualização) | `changes.py` | Médio |
| 7 | Produto | O radar não guarda histórico: não dá para saber se um sinal é novo, persistente ou deixou de aparecer | só há a origem atual em `gold/mudancas` | Médio |

## Priorização da rodada

| Oportunidade | Impacto analítico | Usuário | Portfólio | Complexidade | Risco estat. | Risco priv. | Manutenção | Decisão |
|---|---|---|---|---|---|---|---|---|
| Correções de privacidade 1–4 | — | Alto | Alto | Baixa | — | **reduz** | Baixa | **Agora** |
| Detector com sazonalidade municipal + FDR + avaliação comparativa | Alto | Médio | Alto | Média | Alto (mitigado por avaliação) | — | Média | **Agora** (adotar só se houver ganho) |
| Histórico do radar (snapshots) | Médio | Alto | Alto | Média | Baixo | Baixo | Média | **Agora**, só para tipos calculados no pipeline |
| B. Decomposição das variações | Alto | Alto | Médio | Baixa | Baixo | Médio (supressão) | Baixa | **Agora** |
| C. Robustez das conclusões | Alto | Alto | Alto | Média | Baixo | Baixo | Baixa | **Agora** |
| A. Municípios semelhantes | Médio | Médio | Médio | Alta | Alto (definir similaridade) | Baixo | Média | Adiado: exige validar a métrica de similaridade |
| D. Cobertura | Médio | Médio | Baixo | Baixa | — | — | Baixa | Parcial (já existe aviso no mapa); reforço pontual |
| E. Perguntas guiadas / chatbot | Baixo | Médio | Médio | Alta | Alto | Médio | Alta | Descartado nesta rodada: radar + robustez já guiam a investigação |
| Privacidade diferencial formal | Alto | — | Alto | Alta | — | reduz | Alta | Documentado (modelo de ameaça e desenho); fora do escopo |
