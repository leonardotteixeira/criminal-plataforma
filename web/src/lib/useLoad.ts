import { useCallback, useEffect, useState } from "react";
import { errorMessage } from "@/lib/api";

export type LoadState<T> = {
  data: T | undefined;
  error: string | undefined;
  loading: boolean;
  retry: () => void;
};

/**
 * Carrega dados quando as dependências mudam. Ignora respostas antigas (corrida entre filtros) e
 * nunca fica em carregamento infinito: termina em `data` ou `error`, com `retry` para o usuário.
 * Passe `enabled = false` para não buscar (ex.: parâmetros ainda indisponíveis).
 */
export function useLoad<T>(
  fn: () => Promise<T>,
  deps: unknown[],
  enabled = true,
): LoadState<T> {
  const key = JSON.stringify(deps);
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<{ key: string; data?: T; error?: string }>(
    { key: "" },
  );
  const fullKey = `${key}#${attempt}`;
  useEffect(() => {
    if (!enabled) return;
    let live = true;
    fn()
      .then((data) => live && setState({ key: fullKey, data }))
      .catch((e) => live && setState({ key: fullKey, error: errorMessage(e) }));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fullKey, enabled]);
  const current = state.key === fullKey;
  const retry = useCallback(() => setAttempt((a) => a + 1), []);
  return {
    data: current ? state.data : undefined,
    error: current ? state.error : undefined,
    loading: enabled && !current,
    retry,
  };
}
