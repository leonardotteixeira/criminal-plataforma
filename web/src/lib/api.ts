import { brand } from "@/config/brand";

export type Categoria = { id: string; nome: string };
export type Meta = {
  marca: string;
  dados_ate: string;
  completo_ate: string;
  k_min: number;
  categorias: string[];
  avisos: string[];
};
export type Cell = { h3: string; n: number };
export type Heatmap = {
  inicio: string;
  fim: string;
  categoria: string | null;
  k_min: number;
  celulas_total: number;
  celulas_suprimidas: number;
  cells: Cell[];
};
export type MunicipioRow = {
  cd_ibge: number;
  municipio: string;
  populacao_2022: number | null;
  ocorrencias: number | null;
  suprimido: boolean;
  taxa_100k: number | null;
};
export type Page<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};

async function get<T>(
  path: string,
  params: Record<string, string | number | undefined> = {},
) {
  const url = new URL(path, brand.apiUrl);
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") url.searchParams.set(k, String(v));
  }
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  return (await res.json()) as T;
}

export const api = {
  meta: () => get<Meta>("/v1/meta"),
  categorias: () => get<Categoria[]>("/v1/categorias"),
  heatmap: (p: { categoria?: string; inicio?: string; fim?: string }) =>
    get<Heatmap>("/v1/heatmap/h3", p),
  municipios: (p: {
    categoria?: string;
    inicio?: string;
    fim?: string;
    page_size?: number;
  }) => get<Page<MunicipioRow>>("/v1/municipios", p),
};

export type Tendencia = {
  completo_ate: string;
  serie: { mes: string; n: number }[];
  sazonalidade: { mes: number; indice: number }[];
  variacao_12m_pct: number | null;
  inclinacao_pct_ano: number | null;
  suprimido: boolean;
  nota: string;
};
export type HourDow = { dow: number; hora: number; n: number };
export type Anomalia = {
  nivel: string;
  id: string;
  nome: string | null;
  categoria: string;
  semana: string;
  n: number;
  esperado: number;
  z: number;
  razao: number;
};
export type Anomalias = {
  semana_completa_ate: string;
  metodo: string;
  itens: Anomalia[];
};
export type ComparacaoPeriodos = {
  a: number | null;
  b: number | null;
  variacao_pct: number | null;
  suprimido: boolean;
};

export const analysis = {
  tendencia: (p: { categoria?: string; cd_ibge?: number }) =>
    get<Tendencia>("/v1/tendencia", p),
  horaDia: (p: { categoria?: string; cd_ibge?: number }) =>
    get<HourDow[]>("/v1/hora-dia", p),
  anomalias: (p: { categoria?: string; limit?: number }) =>
    get<Anomalias>("/v1/anomalias", { nivel: "municipio", ...p }),
  comparar: (p: Record<string, string | number | undefined>) =>
    get<ComparacaoPeriodos>("/v1/comparacao/periodos", p),
};

export type PrevisaoCell = {
  h3: string;
  esperado_4s: number;
  faixa: "alta" | "media" | "baixa";
};
export type Previsao = {
  categoria: string;
  origem: string;
  inicio_previsao: string;
  fim_previsao: string;
  celulas: PrevisaoCell[];
  aviso: string;
};
export type ModeloMetrica = {
  modelo: string;
  desvio_poisson: number;
  mae: number;
  captura_top10: number;
  origens_melhor_que_media12_pct: number;
  n_obs: number;
  n_origens: number;
};
export type Backtest = {
  categoria: string;
  metodo: string;
  modelos: ModeloMetrica[];
  calibracao: { decil: number; previsto: number; observado: number }[];
  reducao_desvio_vs_media12_pct: number;
  ganho_captura_vs_media12_pp: number;
  captura_teto_oraculo: number;
  leitura: string;
};

export const forecast = {
  previsao: (categoria: string) =>
    get<Previsao>("/v1/previsao/h3", { categoria }),
  backtest: (categoria: string) =>
    get<Backtest>("/v1/previsao/backtest", { categoria }),
};
