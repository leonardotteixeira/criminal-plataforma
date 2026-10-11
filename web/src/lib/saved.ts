// Análises salvas: só no navegador (localStorage). Sem conta, sem servidor.
// Cada item guarda a URL (que contém os filtros) e a data dos dados no momento de salvar,
// para avisar quando a base foi atualizada depois disso.

export type SavedView = {
  id: string;
  titulo: string;
  url: string;
  salvo_em: string;
  dados_ate: string;
};

const KEY = "sinalbr:analises";

export function loadSaved(): SavedView[] {
  try {
    const raw = localStorage.getItem(KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function store(items: SavedView[]): boolean {
  try {
    localStorage.setItem(KEY, JSON.stringify(items));
    window.dispatchEvent(new Event("sinalbr:analises"));
    return true;
  } catch {
    return false;
  }
}

/** Salva (ou atualiza, se a mesma URL já existir). Retorna false se o navegador bloquear. */
export function saveView(v: Omit<SavedView, "id" | "salvo_em">): boolean {
  const items = loadSaved().filter((x) => x.url !== v.url);
  items.unshift({
    ...v,
    id: crypto.randomUUID(),
    salvo_em: new Date().toISOString(),
  });
  return store(items.slice(0, 30));
}

export function removeView(id: string): boolean {
  return store(loadSaved().filter((x) => x.id !== id));
}

/** A base foi reprocessada com dados mais novos depois que a análise foi salva? */
export function dadosAtualizados(
  v: SavedView,
  dadosAteAtual: string | undefined,
): boolean {
  return !!dadosAteAtual && dadosAteAtual > v.dados_ate;
}
