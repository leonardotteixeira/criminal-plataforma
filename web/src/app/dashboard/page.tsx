"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import {
  AlertsTab,
  CATS_PREVISAO,
  CompareBox,
  ForecastTab,
  TimeTab,
} from "@/components/AnalysisTabs";
import { AppHeader } from "@/components/AppHeader";
import { MunicipioPicker } from "@/components/MunicipioPicker";
import { SaveViewButton } from "@/components/SavedViews";
import {
  buttonClass,
  fmtDate,
  fmtInt,
  fmtNum,
  Notice,
  selectClass,
} from "@/components/ui";
import { brand, disclaimers } from "@/config/brand";
import {
  analysis,
  api,
  buildUrl,
  errorMessage,
  forecast,
  municipiosLista,
  type Categoria,
  type Heatmap,
  type Meta,
  type MunicipioRef,
  type MunicipioRow,
  type Previsao,
} from "@/lib/api";
import { monthsBack } from "@/lib/dates";

const HeatMap = dynamic(
  () => import("@/components/HeatMap").then((m) => m.HeatMap),
  {
    ssr: false,
    loading: () => <div className="h-full w-full animate-pulse bg-border/40" />,
  },
);

const PERIODOS = [3, 6, 12, 24];
type Tab = "geral" | "tempo" | "alertas" | "previsao";
const TABS: { id: Tab; label: string }[] = [
  { id: "geral", label: "Visão geral" },
  { id: "tempo", label: "Tempo" },
  { id: "alertas", label: "Alertas" },
  { id: "previsao", label: "Previsão" },
];

// Todo o estado relevante fica na URL (?categoria=&meses=&aba=&municipio=): links e análises
// salvas reproduzem exatamente a mesma visão.
function DashboardInner() {
  const sp = useSearchParams();
  const router = useRouter();
  const path = usePathname();
  const [meta, setMeta] = useState<Meta | null>(null);
  const [cats, setCats] = useState<Categoria[]>([]);
  const [categoria, setCategoria] = useState(sp.get("categoria") ?? "roubo");
  const [meses, setMeses] = useState(
    PERIODOS.includes(Number(sp.get("meses"))) ? Number(sp.get("meses")) : 12,
  );
  const [tab, setTab] = useState<Tab>(
    TABS.find((x) => x.id === sp.get("aba"))?.id ?? "geral",
  );
  const [sel, setSel] = useState<MunicipioRef | null>(null);
  const [selId, setSelId] = useState<number | null>(
    Number(sp.get("municipio")) || null,
  );
  const [heat, setHeat] = useState<Heatmap | null>(null);
  const [rank, setRank] = useState<MunicipioRow[]>([]);
  const [cobertura, setCobertura] = useState<Record<string, number>>({});
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
      .catch((e) => setError(errorMessage(e)));
    // Cobertura do mapa por categoria (arquivo mais recente) para a legenda; opcional.
    analysis
      .qualidade()
      .then((q) => {
        const ano = Math.max(...q.categorias.map((c) => c.ano));
        setCobertura(
          Object.fromEntries(
            q.categorias
              .filter((c) => c.ano === ano)
              .map((c) => [c.categoria, c.coord_valida_pct]),
          ),
        );
      })
      .catch(() => setCobertura({}));
  }, []);

  // Resolve o município vindo da URL para exibir o nome.
  useEffect(() => {
    if (selId == null || sel?.cd_ibge === selId) return;
    municipiosLista()
      .then((l) => setSel(l.find((m) => m.cd_ibge === selId) ?? null))
      .catch(() => setSel(null));
  }, [selId, sel]);

  useEffect(() => {
    const p = new URLSearchParams({
      categoria,
      meses: String(meses),
      aba: tab,
    });
    if (selId) p.set("municipio", String(selId));
    router.replace(`${path}?${p}`, { scroll: false });
  }, [categoria, meses, tab, selId, path, router]);

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
      .catch((e) => setError(errorMessage(e)));
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
        setError(errorMessage(e));
        setLoadedKey(`${categoria}|${meses}`);
      });
  }, [meta, categoria, meses]);

  const escolher = (m: MunicipioRef | null) => {
    setSel(m);
    setSelId(m?.cd_ibge ?? null);
  };
  const showForecast = tab === "previsao" && prev?.cat === categoria;
  const total = heat?.cells.reduce((s, c) => s + c.n, 0) ?? 0;
  const nomeCat = cats.find((c) => c.id === categoria)?.nome ?? categoria;
  const cob = cobertura[categoria];
  const inicio = meta ? monthsBack(meta.dados_ate, meses) : null;
  const csvUrl = meta
    ? buildUrl("/v1/export/municipios.csv", {
        categoria,
        inicio: inicio!,
        fim: meta.dados_ate,
      })
    : null;
  const tituloVisao = `${nomeCat}, ${meses} meses${sel ? `, ${sel.municipio}` : ""} (${TABS.find((t) => t.id === tab)?.label})`;

  return (
    <div className="flex h-dvh flex-col">
      <AppHeader
        actions={
          <>
            <Link
              href={`/relatorio?categoria=${categoria}&meses=${meses}${selId ? `&municipio=${selId}` : ""}`}
              className={buttonClass}
            >
              Relatório
            </Link>
            {csvUrl && (
              <a
                className={`${buttonClass} hidden sm:inline-flex`}
                href={csvUrl}
              >
                CSV
              </a>
            )}
            <span className="hidden md:inline-flex">
              <SaveViewButton titulo={tituloVisao} dadosAte={meta?.dados_ate} />
            </span>
          </>
        }
      />

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <main className="relative min-h-[55vh] flex-1">
          <div className="absolute left-2 right-14 top-2 z-10 flex flex-wrap gap-2 rounded-lg border border-border bg-surface/95 p-2 shadow sm:left-3 sm:right-auto sm:top-3">
            <label className="min-w-0 flex-1 text-xs text-muted sm:w-40 sm:flex-none">
              Tipo de crime
              <select
                className={selectClass}
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
            <label className="min-w-0 flex-1 text-xs text-muted sm:w-32 sm:flex-none">
              Período (últimos)
              <select
                className={selectClass}
                value={meses}
                onChange={(e) => setMeses(Number(e.target.value))}
              >
                {PERIODOS.map((p) => (
                  <option key={p} value={p}>
                    {p} meses
                  </option>
                ))}
              </select>
            </label>
            <div className="w-full sm:w-52">
              <MunicipioPicker
                label="Município (análises ao lado)"
                value={selId}
                onChange={escolher}
                compact
              />
            </div>
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
          <p className="pointer-events-none absolute right-14 top-3 hidden max-w-[17rem] rounded-md border border-border bg-surface/90 p-2 text-xs text-muted shadow md:block">
            {showForecast ? (
              <>
                <strong className="text-foreground">
                  Previsão experimental
                </strong>{" "}
                (próximas 4 semanas), células de ~5 km². Não é registro
                observado.
              </>
            ) : (
              <>
                <strong className="text-foreground">
                  Registros observados
                </strong>{" "}
                de {nomeCat.toLowerCase()},{" "}
                {heat ? `${fmtDate(heat.inicio)} a ${fmtDate(heat.fim)}` : "…"}.
                Contagens arredondadas para múltiplos de{" "}
                {meta?.arredondamento_celulas ?? 5}.
                {cob != null && (
                  <>
                    {" "}
                    O mapa cobre{" "}
                    <strong className="text-foreground">
                      {fmtNum(cob, 0)}%
                    </strong>{" "}
                    dos registros deste tipo.
                  </>
                )}
              </>
            )}
          </p>
          {loading && (
            <div
              role="status"
              className="absolute bottom-8 left-1/2 -translate-x-1/2 rounded bg-surface px-3 py-1.5 text-xs shadow"
            >
              Carregando…
            </div>
          )}
        </main>

        <aside className="w-full overflow-y-auto border-t border-border bg-surface p-4 lg:w-[26rem] lg:border-l lg:border-t-0">
          {error && (
            <Notice
              tone="error"
              title="Não foi possível carregar os dados"
              className="mb-3"
            >
              {error}
            </Notice>
          )}
          {cob != null && cob < 60 && !showForecast && (
            <Notice
              tone="warning"
              title="Mapa parcial para este tipo"
              className="mb-3"
            >
              Só {fmtNum(cob, 0)}% dos registros de {nomeCat.toLowerCase()} têm
              local utilizável. Prefira séries e taxas por município.
            </Notice>
          )}
          <div
            role="tablist"
            aria-label="Análises"
            className="mb-4 flex gap-1 rounded-lg bg-background p-1 text-sm"
          >
            {TABS.map((t) => (
              <button
                key={t.id}
                role="tab"
                aria-selected={tab === t.id}
                className={`flex-1 rounded-md px-2 py-1.5 ${tab === t.id ? "bg-surface font-semibold shadow-sm" : "text-muted hover:text-foreground"}`}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>
          {meta && tab === "tempo" && (
            <TimeTab
              categoria={categoria}
              cdIbge={selId}
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
              cdIbge={selId}
              municipio={sel?.municipio ?? null}
              completoAte={meta.completo_ate}
            />
          )}
          {tab === "geral" && (
            <>
              <h2 className="text-sm font-semibold">Resumo do mapa</h2>
              <dl className="mt-2 grid grid-cols-2 gap-3 text-sm">
                <div>
                  <dt className="text-muted">
                    Registros nos hexágonos exibidos (aprox.)
                  </dt>
                  <dd className="text-xl font-semibold tabular-nums">
                    ≈ {fmtInt(total)}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted">
                    Hexágonos ocultos (&lt; {meta?.k_min ?? 5})
                  </dt>
                  <dd className="text-xl font-semibold tabular-nums">
                    {fmtInt(heat?.celulas_suprimidas ?? 0)}
                  </dd>
                </div>
              </dl>
              {meta && (
                <p className="mt-2 text-xs text-muted">
                  Dados até {fmtDate(meta.dados_ate)}; completos até{" "}
                  {fmtDate(meta.completo_ate)}. O mês mais recente está
                  incompleto.
                </p>
              )}

              <h2 className="mt-6 text-sm font-semibold">
                Municípios com maior taxa por 100 mil hab.
              </h2>
              <ol className="mt-2 space-y-1 text-sm">
                {rank.map((m, i) => (
                  <li key={m.cd_ibge}>
                    <button
                      type="button"
                      aria-pressed={selId === m.cd_ibge}
                      onClick={() => escolher(selId === m.cd_ibge ? null : m)}
                      className={`flex w-full items-baseline justify-between gap-2 rounded px-1.5 py-0.5 text-left hover:bg-surface-2 ${selId === m.cd_ibge ? "bg-surface-2 font-semibold" : ""}`}
                    >
                      <span>
                        <span className="mr-2 tabular-nums text-muted">
                          {i + 1}.
                        </span>
                        {m.municipio}
                      </span>
                      <span className="tabular-nums">
                        {fmtNum(m.taxa_100k)}
                      </span>
                    </button>
                  </li>
                ))}
              </ol>
              <p className="mt-2 text-xs text-muted">
                Taxa = registros no período ÷ população do Censo 2022.
                Municípios pequenos oscilam muito; um ranking não indica que um
                lugar seja mais perigoso.{" "}
                <Link
                  className="underline"
                  href={selId ? `/comparar?m=${selId}` : "/comparar"}
                >
                  Comparar municípios
                </Link>
              </p>

              {meta && (
                <>
                  <h2 className="mt-6 text-sm font-semibold">
                    {sel ? sel.municipio : "Estado"}: comparação anual
                  </h2>
                  <CompareBox
                    categoria={categoria}
                    cdIbge={selId}
                    municipio={null}
                    completoAte={meta.completo_ate}
                  />
                </>
              )}
            </>
          )}
          <section
            aria-labelledby="limites"
            className="mt-6 rounded-lg border border-border p-3 text-xs text-muted"
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
            <p className="mt-2">
              Confiabilidade por ano e tipo em{" "}
              <Link className="underline" href="/qualidade">
                Qualidade dos dados
              </Link>
              . Fonte: {brand.dataSource}.
            </p>
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
