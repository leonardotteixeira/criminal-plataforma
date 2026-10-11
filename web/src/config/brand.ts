// Marca provisória. Troque aqui (e SINALBR_BRAND na API) para renomear o produto.
export const brand = {
  name: "SinalBR",
  tagline: "Inteligência criminal aberta, agregada e anonimizada",
  description:
    "Plataforma que reúne dados abertos de ocorrências para apoiar análise territorial de segurança pública, sem identificar pessoas.",
  dataSource: "SSP-SP (SPDados) e IBGE",
  apiUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
};

export const disclaimers = [
  "Boletins de ocorrência refletem o registro, não o crime real: há subnotificação, que varia por tipo de crime e por região.",
  "Modelos preditivos podem reforçar vieses de policiamento. Use as análises para entender padrões, não para decidir sobre pessoas.",
  "Dados agregados em hexágonos (~0,7 km²) e municípios; células com poucas ocorrências são ocultadas. Meses recentes são parciais.",
];

// Números reais do piloto (ver docs/qualidade-dados.md e docs/previsao.md). Atualize ao reprocessar.
export const stats = {
  registros: "5,5 mi",
  periodo: "2022–2026",
  municipios: "645",
  kMin: 5,
};
