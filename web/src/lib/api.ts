import { brand } from "@/config/brand";

// ---------------------------------------------------------------- tipos (espelham os schemas da API)
export type Categoria = { id: string; nome: string };
export type Meta = {
  marca: string;
  dados_ate: string;
  completo_ate: string;
  k_min: number;
  fonte_atualizada_em: string | null;
  processado_em: string | null;
  arredondamento_celulas: number;
  categorias: string[];
  avisos: string[];
};
export type Cell = { h3: string; n: number };
export type Heatmap = {
  inicio: string;
  fim: string;
  categoria: string | null;
  k_min: number;
  arredondamento: number;
  celulas_total: number;
  celulas_suprimidas: number;
  cells: Cell[];
};
export type MunicipioRef = {
  cd_ibge: number;
  municipio: string;
  populacao_2022: number | null;
};
export type MunicipioRow = MunicipioRef & {
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
export type RegiaoSerie = {
  cd_ibge: number;
  municipio: string;
  populacao_2022: number | null;
  ocorrencias: number | null;
  taxa_100k: number | null;
  serie_taxa_100k: [string, number][];
};
export type PerfilCategoria = {
  categoria: string;
  n: number | null;
  n_anterior: number | null;
  taxa_100k: number | null;
  variacao_pct: number | null;
  participacao_pct: number | null;
};
export type PerfilMunicipio = MunicipioRef & {
  total: number | null;
  taxa_total_100k: number | null;
  categorias: PerfilCategoria[];
};
export type RazaoTaxas = {
  categoria: string;
  cd_ibge_ref: number;
  cd_ibge: number;
  razao: number;
  ic_inf: number;
  ic_sup: number;
  dispersao: number;
  leitura: string;
};
export type Perfil = {
  inicio: string;
  fim: string;
  inicio_anterior: string;
  fim_anterior: string;
  meses: number;
  municipios: PerfilMunicipio[];
  razoes: RazaoTaxas[];
  nota: string;
};

export type RadarTipo =
  "mudanca_persistente" | "variacao" | "anomalia" | "dados";
export type RadarItem = {
  tipo: RadarTipo;
  categoria: string | null;
  categoria_nome: string | null;
  cd_ibge: number | null;
  municipio: string | null;
  periodo_inicio: string;
  periodo_fim: string;
  titulo: string;
  explicacao: string;
  direcao: "alta" | "queda" | null;
  metricas: Record<string, number | null>;
  forca: number;
};
export type Radar = {
  referencia: string;
  criterios: Record<RadarTipo, string>;
  contagem: Record<RadarTipo, number>;
  itens: RadarItem[];
  aviso: string;
};
export type MudancasAvaliacao = {
  categoria: string;
  series_avaliadas: number;
  sinais: number;
  confirmados_pct: number | null;
  confirmacao_acaso_pct: number | null;
  referencia_confirmados_pct: number | null;
  referencia_confirmacao_acaso_pct: number | null;
  confiavel: boolean;
};
export type Mudancas = {
  referencia: string;
  metodo: string;
  itens: {
    cd_ibge: number;
    municipio: string;
    categoria: string;
    direcao: "alta" | "queda";
    inicio: string;
    semanas: number;
    razao: number;
    observado: number;
    esperado: number;
    confiavel: boolean;
  }[];
  avaliacao: MudancasAvaliacao[];
  simulacao: {
    nivel_semanal: number;
    cenario: string;
    cusum_taxa_sinal: number;
    referencia_taxa_sinal: number;
    cusum_atraso_medio_semanas: number | null;
  }[];
};

export type QualidadeAno = {
  ano: number;
  registros: number;
  coord_valida_pct: number;
  coord_zero_pct: number;
  coord_ausente_pct: number;
  coord_invalida_pct: number;
  sem_hora_pct: number;
  data_imputada_pct: number;
  sem_bairro_pct: number;
  sem_tipo_local_pct: number;
  nao_classificado_pct: number;
  fora_da_janela: number;
  tamanho_mb: number | null;
  fonte_modificada: string | null;
};
export type Qualidade = {
  anos: QualidadeAno[];
  categorias: {
    ano: number;
    categoria: string;
    registros: number;
    coord_valida_pct: number;
    sem_hora_pct: number;
    data_imputada_pct: number;
  }[];
  semanas: {
    semana: string;
    registros: number;
    mediana_8: number | null;
    razao: number | null;
    status: "completa" | "parcial" | "residual";
  }[];
  etapas: {
    ordem: number;
    etapa: string;
    definicao: string;
    registros: number;
  }[];
  execucoes: {
    processado_em: string;
    etapas: string;
    fonte_atualizada_em: string | null;
    dados_ate: string | null;
    semana_completa_ate: string | null;
    registros_silver: number | null;
  }[];
  definicoes: Record<string, string>;
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

// ---------------------------------------------------------------- transporte
/** Erro com mensagem já legível para o usuário (em vez de "Failed to fetch"). */
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number | null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type Params = Record<string, string | number | undefined | (string | number)[]>;

export function buildUrl(path: string, params: Params = {}): string {
  const url = new URL(path, brand.apiUrl);
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === "") continue;
    for (const item of Array.isArray(v) ? v : [v])
      url.searchParams.append(k, String(item));
  }
  return url.toString();
}

async function get<T>(path: string, params: Params = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(buildUrl(path, params), { cache: "no-store" });
  } catch {
    throw new ApiError(
      `Não foi possível conectar à API (${brand.apiUrl}). Verifique se ela está rodando e se esta origem está liberada em SINALBR_CORS.`,
      null,
    );
  }
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail =
        typeof body.detail === "string"
          ? body.detail
          : JSON.stringify(body.detail);
    } catch {
      detail = res.statusText;
    }
    const prefix =
      res.status === 503
        ? "Dados ainda não gerados"
        : res.status >= 500
          ? "Erro interno da API"
          : "Requisição inválida";
    throw new ApiError(`${prefix}: ${detail}`, res.status);
  }
  return (await res.json()) as T;
}

export function errorMessage(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

// ---------------------------------------------------------------- endpoints
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
  municipiosLista: () => get<MunicipioRef[]>("/v1/municipios/lista"),
};

export const analysis = {
  tendencia: (p: { categoria?: string; cd_ibge?: number }) =>
    get<Tendencia>("/v1/tendencia", p),
  horaDia: (p: { categoria?: string; cd_ibge?: number }) =>
    get<HourDow[]>("/v1/hora-dia", p),
  anomalias: (p: { categoria?: string; cd_ibge?: number; limit?: number }) =>
    get<Anomalias>("/v1/anomalias", { nivel: "municipio", ...p }),
  comparar: (p: Record<string, string | number | undefined>) =>
    get<ComparacaoPeriodos>("/v1/comparacao/periodos", p),
  regioes: (p: {
    cd_ibge: number[];
    categoria?: string;
    inicio?: string;
    fim?: string;
  }) => get<RegiaoSerie[]>("/v1/comparacao/regioes", p),
  perfil: (p: { cd_ibge: number[]; meses: number }) =>
    get<Perfil>("/v1/comparacao/perfil", p),
  radar: (p: { categoria?: string; cd_ibge?: number; por_tipo?: number }) =>
    get<Radar>("/v1/radar", p),
  mudancas: (p: { categoria?: string; cd_ibge?: number } = {}) =>
    get<Mudancas>("/v1/mudancas", p),
  qualidade: () => get<Qualidade>("/v1/qualidade"),
};

export const forecast = {
  previsao: (categoria: string) =>
    get<Previsao>("/v1/previsao/h3", { categoria }),
  backtest: (categoria: string) =>
    get<Backtest>("/v1/previsao/backtest", { categoria }),
};

// A lista de municípios não muda durante a sessão: uma única requisição compartilhada.
let municipiosCache: Promise<MunicipioRef[]> | null = null;
export function municipiosLista(): Promise<MunicipioRef[]> {
  municipiosCache ??= api.municipiosLista().catch((e) => {
    municipiosCache = null;
    throw e;
  });
  return municipiosCache;
}
