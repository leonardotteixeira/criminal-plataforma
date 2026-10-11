"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { buttonClass, fmtDate, Notice } from "@/components/ui";
import {
  dadosAtualizados,
  loadSaved,
  removeView,
  saveView,
  type SavedView,
} from "@/lib/saved";

function useSaved() {
  const [items, setItems] = useState<SavedView[]>([]);
  useEffect(() => {
    const sync = () => setItems(loadSaved());
    sync();
    window.addEventListener("sinalbr:analises", sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener("sinalbr:analises", sync);
      window.removeEventListener("storage", sync);
    };
  }, []);
  return items;
}

/** Botão "Salvar visão": guarda a URL atual com um título descritivo. */
export function SaveViewButton({
  titulo,
  dadosAte,
}: {
  titulo: string;
  dadosAte?: string;
}) {
  const [status, setStatus] = useState<"idle" | "ok" | "erro">("idle");
  return (
    <button
      type="button"
      className={buttonClass}
      disabled={!dadosAte}
      onClick={() => {
        const ok = saveView({
          titulo,
          url: window.location.pathname + window.location.search,
          dados_ate: dadosAte!,
        });
        setStatus(ok ? "ok" : "erro");
        setTimeout(() => setStatus("idle"), 2500);
      }}
    >
      <span aria-hidden="true">☆</span>
      {status === "ok"
        ? "Salvo"
        : status === "erro"
          ? "Navegador bloqueou"
          : "Salvar visão"}
      <span className="sr-only" aria-live="polite">
        {status === "ok" ? "Análise salva neste navegador" : ""}
      </span>
    </button>
  );
}

export function SavedViewsList({ dadosAte }: { dadosAte?: string }) {
  const items = useSaved();
  if (!items.length)
    return (
      <p className="text-sm text-muted">
        Nenhuma análise salva. No painel ou no comparador, use “Salvar visão”
        para guardar filtros neste navegador.
      </p>
    );
  return (
    <ul className="divide-y divide-border">
      {items.map((v) => {
        const nova = dadosAtualizados(v, dadosAte);
        return (
          <li
            key={v.id}
            className="flex flex-wrap items-center justify-between gap-2 py-2"
          >
            <div className="min-w-0">
              <Link href={v.url} className="font-medium hover:underline">
                {v.titulo}
              </Link>
              <p className="text-xs text-muted">
                Salva em {fmtDate(v.salvo_em)} · dados até{" "}
                {fmtDate(v.dados_ate)}
                {nova && (
                  <span className="ml-2 rounded bg-warning-bg px-1.5 py-0.5 text-foreground">
                    dados atualizados desde então (até {fmtDate(dadosAte)})
                  </span>
                )}
              </p>
            </div>
            <button
              type="button"
              className="text-xs text-muted hover:text-foreground"
              aria-label={`Remover análise salva ${v.titulo}`}
              onClick={() => removeView(v.id)}
            >
              Remover
            </button>
          </li>
        );
      })}
    </ul>
  );
}

export function SavedNote() {
  return (
    <Notice tone="info" title="Onde ficam as análises salvas">
      Só neste navegador (armazenamento local). Não há conta nem envio para
      servidor; limpar os dados do navegador apaga a lista.
    </Notice>
  );
}
