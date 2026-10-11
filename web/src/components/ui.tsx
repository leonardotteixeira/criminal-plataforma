// Componentes de interface compartilhados. Mantêm hierarquia, espaçamento e estados consistentes.
import Link from "next/link";
import type { ReactNode } from "react";

export const selectClass =
  "mt-1 block w-full min-w-0 rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-foreground";
export const buttonClass =
  "inline-flex items-center justify-center gap-1.5 rounded-md border border-border bg-surface px-3 py-1.5 text-sm font-medium hover:bg-surface-2 disabled:opacity-50";
export const primaryButtonClass =
  "inline-flex items-center justify-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-background hover:opacity-90";

export function Card({
  title,
  description,
  actions,
  children,
  className = "",
}: {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-xl border border-border bg-surface p-4 sm:p-5 ${className}`}
    >
      {(title || actions) && (
        <header className="mb-3 flex flex-wrap items-start justify-between gap-2">
          <div>
            {title && <h2 className="text-base font-semibold">{title}</h2>}
            {description && (
              <p className="mt-0.5 text-sm text-muted">{description}</p>
            )}
          </div>
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}

type NoticeTone = "info" | "warning" | "error";
const TONE: Record<NoticeTone, { cls: string; label: string }> = {
  info: { cls: "border-info/40 bg-info/5", label: "Informação" },
  warning: { cls: "border-warning/50 bg-warning-bg", label: "Atenção" },
  error: { cls: "border-danger/50 bg-danger/5", label: "Erro" },
};

/** Aviso com rótulo textual (a cor nunca é o único sinal). */
export function Notice({
  tone = "info",
  title,
  children,
  className = "",
}: {
  tone?: NoticeTone;
  title?: string;
  children: ReactNode;
  className?: string;
}) {
  const t = TONE[tone];
  return (
    <div
      role={tone === "error" ? "alert" : "note"}
      className={`rounded-lg border p-3 text-sm ${t.cls} ${className}`}
    >
      <p className="font-semibold">{title ?? t.label}</p>
      <div className="mt-0.5 text-foreground/90">{children}</div>
    </div>
  );
}

/** Estados de carregamento, erro e vazio com mensagem útil e ação de nova tentativa. */
export function StateMessage({
  loading,
  error,
  empty,
  emptyText = "Nenhum resultado para os filtros escolhidos.",
  onRetry,
  children,
}: {
  loading?: boolean;
  error?: string;
  empty?: boolean;
  emptyText?: ReactNode;
  onRetry?: () => void;
  children?: ReactNode;
}) {
  if (error)
    return (
      <Notice tone="error" title="Não foi possível carregar">
        <p>{error}</p>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className={`${buttonClass} mt-2`}
          >
            Tentar de novo
          </button>
        )}
      </Notice>
    );
  if (loading)
    return (
      <div role="status" aria-live="polite" className="space-y-2">
        <span className="sr-only">Carregando…</span>
        <div className="h-4 w-2/3 animate-pulse rounded bg-surface-2" />
        <div className="h-4 w-1/2 animate-pulse rounded bg-surface-2" />
        <div className="h-24 w-full animate-pulse rounded bg-surface-2" />
      </div>
    );
  if (empty)
    return (
      <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted">
        {emptyText}
      </p>
    );
  return <>{children}</>;
}

export function Stat({
  label,
  value,
  hint,
}: {
  label: ReactNode;
  value: ReactNode;
  hint?: ReactNode;
}) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="mt-0.5 text-xl font-semibold tabular-nums">{value}</dd>
      {hint && <dd className="text-xs text-muted">{hint}</dd>}
    </div>
  );
}

export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "accent" | "warning";
}) {
  const cls = {
    neutral: "border-border bg-surface-2 text-foreground",
    accent: "border-accent/40 bg-accent/10 text-foreground",
    warning: "border-warning/50 bg-warning-bg text-foreground",
  }[tone];
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${cls}`}
    >
      {children}
    </span>
  );
}

/** Variação com seta e texto, em cor neutra: alta de registros não é "boa" nem "ruim" por si. */
export function Delta({
  value,
  suffix = "%",
}: {
  value: number | null | undefined;
  suffix?: string;
}) {
  if (value == null) return <span className="text-muted">—</span>;
  const arrow = value > 0 ? "▲" : value < 0 ? "▼" : "■";
  const word = value > 0 ? "alta" : value < 0 ? "queda" : "estável";
  return (
    <span className="tabular-nums" title={word}>
      <span aria-hidden="true" className="mr-0.5 text-[0.7em]">
        {arrow}
      </span>
      {value > 0 ? "+" : ""}
      {value.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}
      {suffix}
      <span className="sr-only"> ({word})</span>
    </span>
  );
}

export function TextLink({
  href,
  children,
}: {
  href: string;
  children: ReactNode;
}) {
  return (
    <Link
      href={href}
      className="font-medium text-accent underline-offset-2 hover:underline"
    >
      {children}
    </Link>
  );
}

export const fmtInt = (n: number | null | undefined) =>
  n == null ? "—" : n.toLocaleString("pt-BR");
export const fmtNum = (n: number | null | undefined, d = 1) =>
  n == null ? "—" : n.toLocaleString("pt-BR", { maximumFractionDigits: d });
export const fmtDate = (s: string | null | undefined) =>
  s ? new Date(s.slice(0, 10) + "T00:00:00").toLocaleDateString("pt-BR") : "—";
export const fmtMonth = (s: string) =>
  new Date(s.slice(0, 10) + "T00:00:00").toLocaleDateString("pt-BR", {
    month: "short",
    year: "numeric",
  });
