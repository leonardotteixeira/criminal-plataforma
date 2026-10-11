"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { LineChart } from "@/components/Charts";
import { HexSvgMap } from "@/components/HexSvgMap";
import { scaleMax } from "@/components/scale";
import { brand, disclaimers } from "@/config/brand";
import {
  analysis,
  api,
  type Categoria,
  type ComparacaoPeriodos,
  type Heatmap,
  type Meta,
  type MunicipioRow,
  type Tendencia,
} from "@/lib/api";
import { monthsBack, yearOverYearWindows } from "@/lib/dates";

type Data = {
  meta: Meta;
  cat: Categoria | undefined;
  heat: Heatmap;
  rank: MunicipioRow[];
  tend: Tendencia;
  cmp: ComparacaoPeriodos;
};

const fmt = (n: number | null | undefined) =>
  n == null ? "—" : n.toLocaleString("pt-BR");
const dt = (s: string) => new Date(s + "T00:00:00").toLocaleDateString("pt-BR");

function Report() {
  const sp = useSearchParams();
  const categoria = sp.get("categoria") ?? "roubo";
  const meses = Number(sp.get("meses") ?? 12);
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const [meta, cats] = await Promise.all([api.meta(), api.categorias()]);
      const p = {
        categoria,
        inicio: monthsBack(meta.dados_ate, meses),
        fim: meta.dados_ate,
      };
      const w = yearOverYearWindows(meta.completo_ate);
      const [heat, rank, tend, cmp] = await Promise.all([
        api.heatmap(p),
        api.municipios({ ...p, page_size: 15 }),
        analysis.tendencia({ categoria }),
        analysis.comparar({
          categoria,
          inicio_a: w.iniA,
          fim_a: w.fimA,
          inicio_b: w.iniB,
          fim_b: w.fimB,
        }),
      ]);
      setData({
        meta,
        cat: cats.find((c) => c.id === categoria),
        heat,
        rank: rank.items,
        tend,
        cmp,
      });
    })().catch((e) => setError(String(e.message ?? e)));
  }, [categoria, meses]);

  if (error)
    return (
      <p role="alert" className="p-6 text-red-600">
        Não foi possível gerar o relatório: {error}
      </p>
    );
  if (!data)
    return (
      <p role="status" className="p-6 text-muted">
        Gerando relatório…
      </p>
    );

  const { meta, heat, rank, tend, cmp } = data;
  const total = heat.cells.reduce((s, c) => s + c.n, 0);

  return (
    <main className="mx-auto max-w-3xl px-6 py-8 print:max-w-none print:p-0">
      <div className="mb-6 flex items-center justify-between print:hidden">
        <Link
          href="/dashboard"
          className="text-sm text-muted hover:text-foreground"
        >
          ← Voltar ao painel
        </Link>
        <div className="flex gap-2">
          <a
            className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-surface"
            href={`${brand.apiUrl}/v1/export/municipios.csv?categoria=${categoria}&inicio=${heat.inicio}&fim=${heat.fim}`}
          >
            CSV por município
          </a>
          <a
            className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-surface"
            href={`${brand.apiUrl}/v1/export/celulas.csv?categoria=${categoria}&inicio=${heat.inicio}&fim=${heat.fim}`}
          >
            CSV por hexágono
          </a>
          <button
            type="button"
            onClick={() => window.print()}
            className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-background"
          >
            Imprimir / salvar PDF
          </button>
        </div>
      </div>

      <header className="border-b border-border pb-4">
        <p className="text-sm text-muted">{brand.name} · Relatório</p>
        <h1 className="text-2xl font-semibold tracking-tight">
          {data.cat?.nome ?? categoria} no estado de São Paulo
        </h1>
        <p className="text-sm text-muted">
          Período: {dt(heat.inicio)} a {dt(heat.fim)} · Gerado em{" "}
          {new Date().toLocaleDateString("pt-BR")} · Dados até{" "}
          {dt(meta.dados_ate)} (completos até {dt(meta.completo_ate)})
        </p>
      </header>

      <section className="mt-6 grid grid-cols-3 gap-4" aria-label="Resumo">
        <div>
          <p className="text-xs text-muted">
            Ocorrências nos hexágonos exibidos
          </p>
          <p className="text-2xl font-semibold tabular-nums">{fmt(total)}</p>
        </div>
        <div>
          <p className="text-xs text-muted">
            Hexágonos ocultos (&lt; {meta.k_min})
          </p>
          <p className="text-2xl font-semibold tabular-nums">
            {fmt(heat.celulas_suprimidas)}
          </p>
        </div>
        <div>
          <p className="text-xs text-muted">
            12 meses completos vs. 12 anteriores
          </p>
          <p className="text-2xl font-semibold tabular-nums">
            {cmp.suprimido || cmp.variacao_pct == null
              ? "—"
              : `${cmp.variacao_pct > 0 ? "+" : ""}${fmt(cmp.variacao_pct)}%`}
          </p>
        </div>
      </section>

      <section className="mt-6 break-inside-avoid">
        <h2 className="mb-2 font-semibold">
          Distribuição espacial (hexágonos de ~0,7 km²)
        </h2>
        <HexSvgMap
          cells={heat.cells}
          max={scaleMax(heat.cells)}
          label="Mapa estático de ocorrências por hexágono"
        />
      </section>

      <section className="mt-6 break-inside-avoid">
        <h2 className="mb-2 font-semibold">Série mensal (meses completos)</h2>
        {tend.suprimido ? (
          <p className="text-sm text-muted">
            Série oculta (poucas ocorrências).
          </p>
        ) : (
          <LineChart data={tend.serie} label="Série mensal de ocorrências" />
        )}
      </section>

      <section className="mt-6 break-inside-avoid">
        <h2 className="mb-2 font-semibold">
          Municípios com maior taxa por 100 mil habitantes
        </h2>
        <table className="w-full text-sm">
          <caption className="sr-only">Ranking de municípios por taxa</caption>
          <thead>
            <tr className="border-b border-border text-left text-muted">
              <th scope="col" className="py-1">
                #
              </th>
              <th scope="col">Município</th>
              <th scope="col" className="text-right">
                Ocorrências
              </th>
              <th scope="col" className="text-right">
                Taxa/100 mil
              </th>
            </tr>
          </thead>
          <tbody>
            {rank.map((m, i) => (
              <tr key={m.cd_ibge} className="border-b border-border/50">
                <td className="py-1 text-muted">{i + 1}</td>
                <td>{m.municipio}</td>
                <td className="text-right tabular-nums">
                  {fmt(m.ocorrencias)}
                </td>
                <td className="text-right tabular-nums">{fmt(m.taxa_100k)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-1 text-xs text-muted">
          Taxa = ocorrências registradas ÷ população do Censo 2022. Municípios
          pequenos oscilam muito.
        </p>
      </section>

      <section className="mt-6 break-inside-avoid rounded border border-border p-4 text-xs text-muted">
        <h2 className="mb-1 text-sm font-semibold text-foreground">
          Limitações e método
        </h2>
        <ul className="list-disc space-y-1 pl-4">
          {disclaimers.map((d) => (
            <li key={d}>{d}</li>
          ))}
          <li>
            Fontes: {brand.dataSource}. Métodos em docs/analises.md e
            docs/previsao.md do repositório.
          </li>
        </ul>
      </section>
    </main>
  );
}

export default function RelatorioPage() {
  return (
    <Suspense
      fallback={
        <p role="status" className="p-6">
          Carregando…
        </p>
      }
    >
      <Report />
    </Suspense>
  );
}
