import { brand } from "@/config/brand";

export type Categoria = { id: string; nome: string };
export type Meta = {
  marca: string;
  dados_ate: string;
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
export type Page<T> = { items: T[]; total: number; page: number; page_size: number };

async function get<T>(path: string, params: Record<string, string | number | undefined> = {}) {
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
  municipios: (p: { categoria?: string; inicio?: string; fim?: string; page_size?: number }) =>
    get<Page<MunicipioRow>>("/v1/municipios", p),
};
