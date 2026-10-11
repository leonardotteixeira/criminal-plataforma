"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { ThemeToggle } from "@/components/ThemeToggle";
import { brand } from "@/config/brand";

// Três objetivos: observar (Painel), investigar/acompanhar (Radar), comparar e checar a base.
export const NAV = [
  { href: "/dashboard", label: "Painel", hint: "Mapa, séries e previsão" },
  { href: "/radar", label: "Radar", hint: "O que mudou e merece investigação" },
  { href: "/comparar", label: "Comparar", hint: "Municípios lado a lado" },
  { href: "/qualidade", label: "Qualidade", hint: "Confiabilidade dos dados" },
] as const;

export function AppHeader({ actions }: { actions?: ReactNode }) {
  const path = usePathname();
  return (
    <header className="border-b border-border bg-surface">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2">
        <Link href="/" className="font-semibold tracking-tight">
          {brand.name}
        </Link>
        <nav
          aria-label="Principal"
          className="order-last -mx-1 flex w-full min-w-0 gap-1 overflow-x-auto text-sm sm:order-none sm:w-auto sm:flex-1"
        >
          {NAV.map((n) => {
            const active = path?.startsWith(n.href);
            return (
              <Link
                key={n.href}
                href={n.href}
                title={n.hint}
                aria-current={active ? "page" : undefined}
                className={`whitespace-nowrap rounded-md px-2.5 py-1.5 ${
                  active
                    ? "bg-surface-2 font-semibold text-foreground"
                    : "text-muted hover:text-foreground"
                }`}
              >
                {n.label}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-2 text-sm">
          {actions}
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
