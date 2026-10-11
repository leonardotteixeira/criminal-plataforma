"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { municipiosLista, type MunicipioRef } from "@/lib/api";

const norm = (s: string) =>
  s.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();

/** Filtra por nome ignorando acentos; nomes que começam com o termo vêm primeiro. */
export function filtrarMunicipios(
  lista: MunicipioRef[],
  termo: string,
  limite = 8,
): MunicipioRef[] {
  const t = norm(termo.trim());
  if (!t) return [];
  const comeca: MunicipioRef[] = [];
  const contem: MunicipioRef[] = [];
  for (const m of lista) {
    const n = norm(m.municipio);
    if (n.startsWith(t)) comeca.push(m);
    else if (n.includes(t)) contem.push(m);
  }
  return [...comeca, ...contem].slice(0, limite);
}

/**
 * Combobox acessível (padrão ARIA 1.2) para escolher um município pelo nome.
 * Teclado: ↑/↓ navega, Enter escolhe, Esc fecha.
 */
export function MunicipioPicker({
  label,
  value,
  onChange,
  placeholder = "Todo o estado",
  allowClear = true,
  exclude = [],
  compact = false,
}: {
  label: string;
  value: number | null;
  onChange: (m: MunicipioRef | null) => void;
  placeholder?: string;
  allowClear?: boolean;
  exclude?: number[];
  compact?: boolean;
}) {
  const id = useId();
  const [lista, setLista] = useState<MunicipioRef[]>([]);
  const [erro, setErro] = useState(false);
  const [termo, setTermo] = useState("");
  const [aberto, setAberto] = useState(false);
  const [ativo, setAtivo] = useState(0);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    municipiosLista()
      .then(setLista)
      .catch(() => setErro(true));
  }, []);

  const atual = lista.find((m) => m.cd_ibge === value) ?? null;
  const opcoes = useMemo(
    () =>
      filtrarMunicipios(lista, termo).filter(
        (m) => !exclude.includes(m.cd_ibge),
      ),
    [lista, termo, exclude],
  );

  const escolher = (m: MunicipioRef | null) => {
    onChange(m);
    setTermo("");
    setAberto(false);
  };

  return (
    <div className={`relative ${compact ? "" : "min-w-[12rem]"}`}>
      <label htmlFor={id} className="text-xs text-muted">
        {label}
      </label>
      <div className="mt-1 flex items-center gap-1">
        <input
          ref={input}
          id={id}
          role="combobox"
          aria-expanded={aberto && opcoes.length > 0}
          aria-controls={`${id}-lista`}
          aria-autocomplete="list"
          aria-activedescendant={
            aberto && opcoes[ativo] ? `${id}-o${ativo}` : undefined
          }
          autoComplete="off"
          className="block w-full min-w-0 rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-foreground placeholder:text-muted"
          placeholder={
            erro ? "Lista indisponível" : (atual?.municipio ?? placeholder)
          }
          disabled={erro}
          value={termo}
          onChange={(e) => {
            setTermo(e.target.value);
            setAtivo(0);
            setAberto(true);
          }}
          onFocus={() => setAberto(true)}
          onBlur={() => setTimeout(() => setAberto(false), 120)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setAtivo((a) => Math.min(a + 1, opcoes.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setAtivo((a) => Math.max(a - 1, 0));
            } else if (e.key === "Enter" && opcoes[ativo]) {
              e.preventDefault();
              escolher(opcoes[ativo]);
            } else if (e.key === "Escape") {
              setAberto(false);
              setTermo("");
            }
          }}
        />
        {allowClear && atual && (
          <button
            type="button"
            className="shrink-0 rounded-md border border-border px-2 py-1.5 text-xs hover:bg-surface-2"
            aria-label={`Remover filtro ${atual.municipio}`}
            onClick={() => escolher(null)}
          >
            ✕
          </button>
        )}
      </div>
      {atual && !termo && (
        <p className="sr-only" aria-live="polite">
          Selecionado: {atual.municipio}
        </p>
      )}
      {aberto && termo && (
        <ul
          id={`${id}-lista`}
          role="listbox"
          aria-label={label}
          className="absolute z-30 mt-1 max-h-64 w-full overflow-auto rounded-md border border-border bg-surface py-1 text-sm shadow-lg"
        >
          {opcoes.length === 0 ? (
            <li className="px-3 py-2 text-muted">
              Nenhum município encontrado.
            </li>
          ) : (
            opcoes.map((m, i) => (
              <li
                key={m.cd_ibge}
                id={`${id}-o${i}`}
                role="option"
                aria-selected={i === ativo}
                className={`cursor-pointer px-3 py-1.5 ${i === ativo ? "bg-surface-2" : ""}`}
                onMouseDown={(e) => {
                  e.preventDefault();
                  escolher(m);
                }}
                onMouseEnter={() => setAtivo(i)}
              >
                {m.municipio}
                {m.populacao_2022 != null && (
                  <span className="ml-2 text-xs text-muted">
                    {m.populacao_2022.toLocaleString("pt-BR")} hab.
                  </span>
                )}
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
