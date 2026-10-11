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

### Limites conhecidos da supressão

- Consultas sobrepostas (por exemplo, períodos que diferem em um mês) podem permitir diferenciar contagens pequenas. Mitigação parcial: granularidade mensal mínima e k = 5. Para uso público em produção, avaliar ruído diferencial ou supressão complementar.
- Hexágonos com pouca população residente (áreas industriais, rodovias) podem concentrar ocorrências de um mesmo evento. Interprete com cuidado.

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
