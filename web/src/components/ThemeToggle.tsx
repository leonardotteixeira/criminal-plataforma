"use client";

import { useDark } from "@/lib/useDark";

export function ThemeToggle() {
  const dark = useDark();
  return (
    <button
      type="button"
      aria-label={dark ? "Mudar para tema claro" : "Mudar para tema escuro"}
      aria-pressed={dark}
      className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-background"
      onClick={() => {
        const next = !dark;
        document.documentElement.classList.toggle("dark", next);
        try {
          localStorage.setItem("theme", next ? "dark" : "light");
        } catch {
          /* armazenamento indisponível: o tema vale só para esta sessão */
        }
      }}
    >
      {dark ? "☀ Claro" : "☾ Escuro"}
    </button>
  );
}
