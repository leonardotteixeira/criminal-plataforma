"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import {
  AlertsTab,
  CATS_PREVISAO,
  CompareBox,
  ForecastTab,
  TimeTab,
} from "@/components/AnalysisTabs";
import { monthsBack } from "@/lib/dates";
import { ThemeToggle } from "@/components/ThemeToggle";
import { brand, disclaimers } from "@/config/brand";
import {
  api,
  forecast,
  type Previsao,
  type Categoria,
  type Heatmap,
  type Meta,
  type MunicipioRow,
} from "@/lib/api";

const HeatMap = dynamic(
  () => import("@/components/HeatMap").then((m) => m.HeatMap),
  {
    ssr: false,
    loading: () => <div className="h-full w-full animate-pulse bg-border/40" />,
  },
);

const PERIODOS = [
  { id: 3, label: "3 meses" },
  { id: 6, label: "6 meses" },
  { id: 12, label: "12 meses" },
  { id: 24, label: "24 meses" },
];

type Tab = "geral" | "tempo" | "alertas" | "previsao";
const TABS: Tab[] = ["geral", "tempo", "alertas", "previsao"];

// Estado inicial vem da URL (?categoria=&meses=&aba=), o que torna uma visão compartilhável.
function DashboardInner() {
  const sp = useSearchParams();
  const [meta, setMeta] = useState<Meta | null>(null);
  const [cats, setCats] = useState<Categoria[]>([]);
  const [categoria, setCategoria] = useState(sp.get("categoria") ?? "roubo");
  const [meses, setMeses] = useState(Number(sp.get("meses")) || 12);
  const [heat, setHeat] = useState<Heatmap | null>(null);
  const [rank, setRank] = useState<MunicipioRow[]>([]);
  const [tab, setTab] = useState<Tab>(
    TABS.find((x) => x === sp.get("aba")) ?? "geral",
  );
  const [sel, setSel] = useState<MunicipioRow | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [prev, setPrev] = useState<{ cat: string; data: Previsao } | null>(
    null,
  );
  const [loadedKey, setLoadedKey] = useState<string | null>(null);
  const key = meta ? `${categoria}|${meses}` : null;
  const loading = key !== null && key !== loadedKey;

  useEffect(() => {
    Promise.all([api.meta(), api.categorias()])
      .then(([m, c]) => {
        setMeta(m);
        setCats(c);
      })
      .catch((e) => setError(String(e.message ?? e)));
  }, []);

  useEffect(() => {
    if (
      tab !== "previsao" ||
      !CATS_PREVISAO.includes(categoria) ||
      prev?.cat === categoria
    )
      return;
    forecast
      .previsao(categoria)
      .then((data) => setPrev({ cat: categoria, data }))
      .catch((e) => setError(String(e.message ?? e)));
  }, [tab, categoria, prev]);

  useEffect(() => {
    if (!meta) return;
    const params = {
      categoria,
      inicio: monthsBack(meta.dados_ate, meses),
      fim: meta.dados_ate,
    };
    Promise.all([
      api.heatmap(params),
      api.municipios({ ...params, page_size: 10 }),
    ])
      .then(([h, r]) => {
        setHeat(h);
        setRank(r.items);
        setError(null);
        setLoadedKey(`${categoria}|${meses}`);
      })
      .catch((e) => {
        setError(String(e.message ?? e));
        setLoadedKey(`${categoria}|${meses}`);
      });
  }, [meta, categoria, meses]);

  const showForecast = tab === "previsao" && prev?.cat === categoria;
  const total = heat?.cells.reduce((s, c) => s + c.n, 0) ?? 0;

  return (
    <div className="flex h-dvh flex-col">
      <header className="flex items-center justify-between border-b border-border bg-surface px-4 py-2">
        <Link href="/" className="font-semibold tracking-tight">
          {brand.name} <span className="font-normal text-muted">· Painel</span>
        </Link>
        <nav aria-label="Exportar" className="flex items-center gap-2 text-sm">
          <Link
            href={`/relatorio?categoria=${categoria}&meses=${meses}`}
            className="rounded-md border border-border px-3 py-1.5 hover:bg-background"
          >
            Relatório (PDF)
          </Link>
          {meta && (
            <a
              className="hidden rounded-md border border-border px-3 py-1.5 hover:bg-background sm:inline-block"
              href={`${brand.apiUrl}/v1/export/municipios.csv?categoria=${categoria}&inicio=${monthsBack(meta.dados_ate, meses)}&fim=${meta.dados_ate}`}
            >
              CSV
            </a>
          )}
          <ThemeToggle />
        </nav>
      </header>

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <main className="relative min-h-[50vh] flex-1">
          <div className="absolute left-2 right-14 top-2 z-10 flex gap-2 sm:left-3 sm:right-auto sm:top-3 rounded-lg border border-border bg-surface/95 p-2 shadow">
            <label className="min-w-0 flex-1 text-xs text-muted sm:flex-none">
              Tipo de crime
              <select
                className="mt-0.5 block w-full min-w-0 rounded border border-border bg-surface px-2 py-1 text-sm text-foreground"
                value={categoria}
                onChange={(e) => setCategoria(e.target.value)}
              >
                {cats.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nome}
                  </option>
                ))}
              </select>
            </label>
            <label className="min-w-0 flex-1 text-xs text-muted sm:flex-none">
              Período (últimos)
              <select
                className="mt-0.5 block w-full min-w-0 rounded border border-border bg-surface px-2 py-1 text-sm text-foreground"
                value={meses}
                onChange={(e) => setMeses(Number(e.target.value))}
              >
                {PERIODOS.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <HeatMap
            mode={showForecast ? "previsao" : "contagem"}
            cells={
              showForecast
                ? prev!.data.celulas.map((c) => ({
                    h3: c.h3,
                    n: Math.round(c.esperado_4s),
                    faixa: c.faixa,
                  }))
                : (heat?.cells ?? [])
            }
          />
          {loading && (
            <div
              role="status"
              className="absolute right-14 top-3 rounded bg-surface px-2 py-1 text-xs shadow"
            >
              Carregando…
            </div>
          )}
        </main>

        <aside className="w-full overflow-y-auto border-t border-border bg-surface p-4 lg:w-96 lg:border-l lg:border-t-0">
          {error && (
            <p
              role="alert"
              className="mb-3 rounded border border-red-400 p-2 text-sm text-red-600 dark:text-red-400"
            >
              Não foi possível carregar os dados: {error}
            </p>
          )}
          <div
            role="tablist"
            aria-label="Análises"
            className="mb-4 flex gap-1 rounded-md bg-background p-1 text-sm"
          >
            {(["geral", "tempo", "alertas", "previsao"] as const).map((k) => (
              <button
                key={k}
                role="tab"
                aria-selected={tab === k}
                className={`flex-1 rounded px-2 py-1 ${tab === k ? "bg-surface font-semibold shadow-sm" : "text-muted"}`}
                onClick={() => setTab(k)}
              >
                {
                  {
                    geral: "Visão geral",
                    tempo: "Tempo",
                    alertas: "Alertas",
                    previsao: "Previsão",
                  }[k]
                }
              </button>
            ))}
          </div>
          {meta && tab === "tempo" && (
            <TimeTab
              categoria={categoria}
              cdIbge={sel?.cd_ibge ?? null}
              municipio={sel?.municipio ?? null}
              completoAte={meta.completo_ate}
            />
          )}
          {tab === "previsao" && (
            <ForecastTab
              categoria={categoria}
              previsao={prev?.cat === categoria ? prev.data : null}
            />
          )}
          {meta && tab === "alertas" && (
            <AlertsTab
              categoria={categoria}
              cdIbge={null}
              municipio={null}
              completoAte={meta.completo_ate}
            />
          )}
          {tab === "geral" && (
            <>
              <h2 className="text-sm font-semibold">Resumo</h2>
              <dl className="mt-2 grid grid-cols-2 gap-3 text-sm">
                <div>
                  <dt className="text-muted">
                    Ocorrências nos hexágonos exibidos
                  </dt>
                  <dd className="text-xl font-semibold tabular-nums">
                    {total.toLocaleString("pt-BR")}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted">
                    Hexágonos ocultos (&lt; {meta?.k_min ?? 5})
                  </dt>
                  <dd className="text-xl font-semibold tabular-nums">
                    {(heat?.celulas_suprimidas ?? 0).toLocaleString("pt-BR")}
                  </dd>
                </div>
              </dl>
              {meta && (
                <p className="mt-2 text-xs text-muted">
                  Dados até{" "}
                  {new Date(meta.dados_ate + "T00:00:00").toLocaleDateString(
                    "pt-BR",
                  )}
                  . Os meses mais recentes estão incompletos.
                </p>
              )}

              <h2 className="mt-6 text-sm font-semibold">
                Municípios com maior taxa por 100 mil hab.
              </h2>
              <ol className="mt-2 space-y-1.5 text-sm">
                {rank.map((m, i) => (
                  <li key={m.cd_ibge}>
                    <button
                      type="button"
                      aria-pressed={sel?.cd_ibge === m.cd_ibge}
                      onClick={() =>
                        setSel(sel?.cd_ibge === m.cd_ibge ? null : m)
                      }
                      className={`flex w-full items-baseline justify-between gap-2 rounded px-1 text-left hover:bg-background ${sel?.cd_ibge === m.cd_ibge ? "bg-background font-semibold" : ""}`}
                    >
                      <span>
                        <span className="mr-2 tabular-nums text-muted">
                          {i + 1}.
                        </span>
                        {m.municipio}
                      </span>
                      <span className="tabular-nums">
                        {m.taxa_100k?.toLocaleString("pt-BR") ?? "—"}
                      </span>
                    </button>
                  </li>
                ))}
              </ol>
              <p className="mt-2 text-xs text-muted">
                Taxa = ocorrências registradas no período ÷ população do Censo
                2022. Municípios pequenos oscilam muito; compare com cautela.
              </p>

              {meta && (
                <CompareBox
                  categoria={categoria}
                  cdIbge={sel?.cd_ibge ?? null}
                  municipio={null}
                  completoAte={meta.completo_ate}
                />
              )}
            </>
          )}
          <section
            aria-labelledby="limites"
            className="mt-6 rounded-md border border-border p-3 text-xs text-muted"
          >
            <h2
              id="limites"
              className="mb-1 text-sm font-semibold text-foreground"
            >
              Limitações
            </h2>
            <ul className="list-disc space-y-1 pl-4">
              {disclaimers.map((d) => (
                <li key={d}>{d}</li>
              ))}
            </ul>
          </section>
        </aside>
      </div>
    </div>
  );
}

export default function Dashboard() {
  return (
    <Suspense
      fallback={
        <p role="status" className="p-6">
          Carregando…
        </p>
      }
    >
      <DashboardInner />
    </Suspense>
  );
}
