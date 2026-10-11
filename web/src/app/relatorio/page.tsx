"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { LineChart, YearOverlay } from "@/components/Charts";
import { HexSvgMap } from "@/components/HexSvgMap";
import { scaleMax } from "@/components/scale";
import {
  buttonClass,
  Delta,
  fmtDate,
  fmtInt,
  fmtNum,
  primaryButtonClass,
} from "@/components/ui";
import { brand, disclaimers } from "@/config/brand";
import {
  analysis,
  api,
  buildUrl,
  errorMessage,
  municipiosLista,
  type Categoria,
  type Heatmap,
  type Meta,
  type MunicipioRef,
  type MunicipioRow,
  type Qualidade,
  type Radar,
  type Tendencia,
} from "@/lib/api";
import { monthsBack, yearOverYearWindows } from "@/lib/dates";

type CatLinha = {
  categoria: string;
  nome: string;
  atual: number | null;
  anterior: number | null;
  variacao: number | null;
};

type Dados = {
  meta: Meta;
  cats: Categoria[];
  regiao: MunicipioRef | null;
  popEstado: number;
  heat: Heatmap | null;
  rank: MunicipioRow[];
  tend: Tendencia;
  linhas: CatLinha[];
  estadoCat: { atual: number | null; anterior: number | null };
  radar: Radar | null;
  qual: Qualidade | null;
  janela: { iniA: string; fimA: string; iniB: string; fimB: string };
};

async function carregar(
  categoria: string,
  meses: number,
  cd: number | null,
): Promise<Dados> {
  const [meta, cats, lista] = await Promise.all([
    api.meta(),
    api.categorias(),
    municipiosLista(),
  ]);
  const regiao = cd ? (lista.find((m) => m.cd_ibge === cd) ?? null) : null;
  if (cd && !regiao) throw new Error(`Município ${cd} não encontrado.`);
  const popEstado = lista.reduce((s, m) => s + (m.populacao_2022 ?? 0), 0);
  const janela = yearOverYearWindows(meta.completo_ate);
  const periodo = {
    categoria,
    inicio: monthsBack(meta.dados_ate, meses),
    fim: meta.dados_ate,
  };
  const cmp = (c: string, cdIbge?: number) =>
    analysis.comparar({
      categoria: c,
      cd_ibge: cdIbge,
      inicio_a: janela.iniA,
      fim_a: janela.fimA,
      inicio_b: janela.iniB,
      fim_b: janela.fimB,
    });
  const [heat, rank, tend, porCat, estadoCat, radar, qual] = await Promise.all([
    regiao ? Promise.resolve(null) : api.heatmap(periodo),
    regiao
      ? Promise.resolve({ items: [] as MunicipioRow[] })
      : api.municipios({ ...periodo, page_size: 10 }),
    analysis.tendencia({ categoria, cd_ibge: cd ?? undefined }),
    Promise.all(cats.map((c) => cmp(c.id, cd ?? undefined))),
    cmp(categoria),
    // Seções opcionais: se a etapa do pipeline não existir, o relatório informa em vez de falhar.
    analysis
      .radar({ categoria, cd_ibge: cd ?? undefined, por_tipo: 5 })
      .catch(() => null),
    analysis.qualidade().catch(() => null),
  ]);
  return {
    meta,
    cats,
    regiao,
    popEstado,
    heat,
    rank: rank.items,
    tend,
    linhas: cats.map((c, i) => ({
      categoria: c.id,
      nome: c.nome,
      atual: porCat[i].b,
      anterior: porCat[i].a,
      variacao: porCat[i].variacao_pct,
    })),
    estadoCat: { atual: estadoCat.b, anterior: estadoCat.a },
    radar,
    qual,
    janela,
  };
}

function Secao({
  n,
  titulo,
  children,
}: {
  n: number;
  titulo: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mt-7 break-inside-avoid">
      <h2 className="mb-2 text-lg font-semibold">
        <span className="mr-2 tabular-nums text-muted">{n}.</span>
        {titulo}
      </h2>
      {children}
    </section>
  );
}

function Report() {
  const sp = useSearchParams();
  const categoria = sp.get("categoria") ?? "roubo";
  const meses = Number(sp.get("meses") ?? 12) || 12;
  const cd = Number(sp.get("municipio")) || null;
  const [d, setD] = useState<Dados | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    carregar(categoria, meses, cd)
      .then(setD)
      .catch((e) => setError(errorMessage(e)));
  }, [categoria, meses, cd]);

  if (error)
    return (
      <p role="alert" className="p-6 text-danger">
        Não foi possível gerar o relatório: {error}
      </p>
    );
  if (!d)
    return (
      <p role="status" className="p-6 text-muted">
        Gerando relatório…
      </p>
    );

  const nome = d.cats.find((c) => c.id === categoria)?.nome ?? categoria;
  const regiaoNome = d.regiao ? d.regiao.municipio : "Estado de São Paulo";
  const pop = d.regiao ? d.regiao.populacao_2022 : d.popEstado;
  const linha = d.linhas.find((l) => l.categoria === categoria)!;
  const taxa = linha.atual != null && pop ? (linha.atual * 1e5) / pop : null;
  const taxaEstado =
    d.estadoCat.atual != null ? (d.estadoCat.atual * 1e5) / d.popEstado : null;
  const varEstado =
    d.estadoCat.atual != null && d.estadoCat.anterior
      ? (d.estadoCat.atual / d.estadoCat.anterior - 1) * 100
      : null;
  const totalAtual = d.linhas.reduce((s, l) => s + (l.atual ?? 0), 0);
  const parciais = d.qual?.semanas.filter((s) => s.status !== "completa") ?? [];
  const anoQual = d.qual
    ? Math.max(...d.qual.categorias.map((c) => c.ano))
    : null;
  const qCat = d.qual?.categorias.find(
    (c) => c.ano === anoQual && c.categoria === categoria,
  );
  const radarItens = d.radar?.itens.filter((i) => i.tipo !== "dados") ?? [];
  const versao = `fonte ${fmtDate(d.meta.fonte_atualizada_em)} · processado ${fmtDate(d.meta.processado_em)}`;
  const sinal = (v: number) => `${v > 0 ? "+" : ""}${fmtNum(v)}%`;

  // Resumo executivo: frases montadas só com números calculados; nenhuma atribui causa.
  const resumo: string[] = [];
  if (linha.atual != null) {
    resumo.push(
      `Entre ${fmtDate(d.janela.iniB)} e ${fmtDate(d.janela.fimB)} (12 meses completos), ${regiaoNome} teve ` +
        `${fmtInt(linha.atual)} registros de ${nome.toLowerCase()}` +
        (taxa != null ? ` (${fmtNum(taxa)} por 100 mil habitantes).` : "."),
    );
  } else {
    resumo.push(
      `${regiaoNome} teve menos de ${d.meta.k_min} registros de ${nome.toLowerCase()} no período: valores suprimidos.`,
    );
  }
  if (linha.variacao != null)
    resumo.push(
      `Em relação aos 12 meses anteriores, a variação foi de ${sinal(linha.variacao)}` +
        (d.regiao && varEstado != null
          ? `, contra ${sinal(varEstado)} no estado.`
          : "."),
    );
  if (d.regiao && taxa != null && taxaEstado != null)
    resumo.push(
      `A taxa de registro do município equivale a ${fmtNum(taxa / taxaEstado, 2)} vez(es) a do estado no mesmo período.`,
    );
  if (d.radar)
    resumo.push(
      radarItens.length
        ? `O radar sinaliza ${radarItens.length} observação(ões) para este recorte (seção 8).`
        : "O radar não sinaliza mudanças persistentes, variações fora do padrão estadual nem picos recentes para este recorte.",
    );
  if (qCat && qCat.coord_valida_pct < 60)
    resumo.push(
      `Só ${fmtNum(qCat.coord_valida_pct, 0)}% dos registros deste tipo têm local utilizável; a análise territorial é parcial.`,
    );

  return (
    <main className="mx-auto max-w-3xl px-6 py-8 print:max-w-none print:p-0">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-2 print:hidden">
        <Link
          href={`/dashboard?categoria=${categoria}&meses=${meses}${cd ? `&municipio=${cd}` : ""}`}
          className="text-sm text-muted hover:text-foreground"
        >
          ← Voltar ao painel
        </Link>
        <div className="flex flex-wrap gap-2">
          <a
            className={buttonClass}
            href={buildUrl("/v1/export/municipios.csv", {
              categoria,
              inicio: monthsBack(d.meta.dados_ate, meses),
              fim: d.meta.dados_ate,
            })}
          >
            CSV por município
          </a>
          {!d.regiao && d.heat && (
            <a
              className={buttonClass}
              href={buildUrl("/v1/export/celulas.csv", {
                categoria,
                inicio: d.heat.inicio,
                fim: d.heat.fim,
              })}
            >
              CSV por hexágono
            </a>
          )}
          <button
            type="button"
            onClick={() => window.print()}
            className={primaryButtonClass}
          >
            Imprimir / salvar PDF
          </button>
        </div>
      </div>

      {/* 1. Identificação */}
      <header className="border-b border-border pb-4">
        <p className="text-sm text-muted">
          <span className="mr-2 tabular-nums">1.</span>
          {brand.name} · Relatório analítico
        </p>
        <h1 className="text-2xl font-semibold tracking-tight">
          {nome} — {regiaoNome}
        </h1>
        <dl className="mt-2 grid grid-cols-1 gap-x-6 gap-y-1 text-sm text-muted sm:grid-cols-2">
          <div>
            <dt className="inline">Período de referência: </dt>
            <dd className="inline text-foreground">
              {fmtDate(d.janela.iniB)} a {fmtDate(d.janela.fimB)}
            </dd>
          </div>
          <div>
            <dt className="inline">Comparado com: </dt>
            <dd className="inline text-foreground">
              {fmtDate(d.janela.iniA)} a {fmtDate(d.janela.fimA)}
            </dd>
          </div>
          <div>
            <dt className="inline">Gerado em: </dt>
            <dd className="inline text-foreground">
              {new Date().toLocaleString("pt-BR")}
            </dd>
          </div>
          <div>
            <dt className="inline">Versão dos dados: </dt>
            <dd className="inline text-foreground">{versao}</dd>
          </div>
        </dl>
      </header>

      <Secao n={2} titulo="Resumo executivo">
        <ul className="list-disc space-y-1 pl-5 text-sm">
          {resumo.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
        <p className="mt-2 text-xs text-muted">
          Frases geradas automaticamente a partir dos números deste relatório.
          Descrevem registros policiais; não indicam causas.
        </p>
      </Secao>

      <Secao n={3} titulo="Indicadores principais">
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div>
            <dt className="text-xs text-muted">Registros (12 meses)</dt>
            <dd className="text-xl font-semibold tabular-nums">
              {fmtInt(linha.atual)}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-muted">Taxa por 100 mil hab.</dt>
            <dd className="text-xl font-semibold tabular-nums">
              {fmtNum(taxa)}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-muted">vs. 12 meses anteriores</dt>
            <dd className="text-xl font-semibold">
              <Delta value={linha.variacao} />
            </dd>
          </div>
          <div>
            <dt className="text-xs text-muted">
              {d.regiao ? "Taxa do estado" : "População (Censo 2022)"}
            </dt>
            <dd className="text-xl font-semibold tabular-nums">
              {d.regiao ? fmtNum(taxaEstado) : fmtInt(pop)}
            </dd>
          </div>
        </dl>
      </Secao>

      <Secao n={4} titulo="Evolução temporal">
        {d.tend.suprimido ? (
          <p className="text-sm text-muted">
            Série oculta (poucas ocorrências).
          </p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <h3 className="mb-1 text-sm font-medium">Registros por mês</h3>
              <LineChart
                data={d.tend.serie}
                label={`Série mensal de ${nome} — ${regiaoNome}`}
              />
            </div>
            <div>
              <h3 className="mb-1 text-sm font-medium">Um traço por ano</h3>
              <YearOverlay
                data={d.tend.serie}
                label={`Comparação entre anos — ${regiaoNome}`}
              />
            </div>
          </div>
        )}
      </Secao>

      <Secao
        n={5}
        titulo="Comparação com o período anterior, por tipo de crime"
      >
        <table className="w-full text-sm">
          <caption className="sr-only">
            Registros por tipo de crime nos dois períodos
          </caption>
          <thead>
            <tr className="border-b border-border text-left text-xs text-muted">
              <th scope="col" className="py-1">
                Tipo
              </th>
              <th scope="col" className="text-right">
                Anterior
              </th>
              <th scope="col" className="text-right">
                Atual
              </th>
              <th scope="col" className="text-right">
                Variação
              </th>
            </tr>
          </thead>
          <tbody>
            {d.linhas.map((l) => (
              <tr
                key={l.categoria}
                className={`border-b border-border/50 ${l.categoria === categoria ? "font-semibold" : ""}`}
              >
                <th scope="row" className="py-1 text-left font-normal">
                  {l.nome}
                </th>
                <td className="text-right tabular-nums">
                  {fmtInt(l.anterior)}
                </td>
                <td className="text-right tabular-nums">{fmtInt(l.atual)}</td>
                <td className="text-right">
                  <Delta value={l.variacao} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-1 text-xs text-muted">
          — = menos de {d.meta.k_min} registros (suprimido).
        </p>
      </Secao>

      <Secao n={6} titulo="Distribuição das categorias (12 meses)">
        <ul className="space-y-1.5 text-sm">
          {d.linhas
            .filter((l) => l.atual != null)
            .sort((a, b) => (b.atual ?? 0) - (a.atual ?? 0))
            .map((l) => {
              const pct = totalAtual ? (100 * (l.atual ?? 0)) / totalAtual : 0;
              return (
                <li key={l.categoria}>
                  <div className="flex justify-between">
                    <span>{l.nome}</span>
                    <span className="tabular-nums text-muted">
                      {fmtNum(pct)}%
                    </span>
                  </div>
                  <div
                    className="h-1.5 rounded bg-surface-2"
                    aria-hidden="true"
                  >
                    <div
                      className="h-1.5 rounded bg-accent"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </li>
              );
            })}
        </ul>
      </Secao>

      <Secao n={7} titulo="Análise territorial">
        {d.regiao ? (
          <p className="text-sm">
            Taxa de {nome.toLowerCase()} em {regiaoNome}:{" "}
            <strong>{fmtNum(taxa)}</strong> por 100 mil hab., contra{" "}
            <strong>{fmtNum(taxaEstado)}</strong> no estado. O mapa por hexágono
            é estadual; veja o recorte no painel.
          </p>
        ) : (
          <>
            {d.heat && (
              <HexSvgMap
                cells={d.heat.cells}
                max={scaleMax(d.heat.cells)}
                label={`Mapa estático de registros de ${nome}`}
              />
            )}
            <p className="mt-1 text-xs text-muted">
              Hexágonos de ~0,7 km²
              {d.heat
                ? `, ${fmtDate(d.heat.inicio)} a ${fmtDate(d.heat.fim)}`
                : ""}
              ; contagens arredondadas para múltiplos de{" "}
              {d.meta.arredondamento_celulas}; células com menos de{" "}
              {d.meta.k_min} ocultas.
            </p>
            <table className="mt-3 w-full text-sm">
              <caption className="mb-1 text-left text-sm font-medium">
                Municípios com maior taxa por 100 mil hab.
              </caption>
              <tbody>
                {d.rank.map((m, i) => (
                  <tr key={m.cd_ibge} className="border-b border-border/50">
                    <td className="py-0.5 text-muted">{i + 1}</td>
                    <td>{m.municipio}</td>
                    <td className="text-right tabular-nums">
                      {fmtInt(m.ocorrencias)}
                    </td>
                    <td className="text-right tabular-nums">
                      {fmtNum(m.taxa_100k)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-1 text-xs text-muted">
              Um ranking de taxas não indica que um lugar seja mais perigoso;
              municípios pequenos oscilam muito.
            </p>
          </>
        )}
      </Secao>

      <Secao n={8} titulo="Anomalias e mudanças relevantes">
        {!d.radar ? (
          <p className="text-sm text-muted">
            Radar indisponível (etapa do pipeline não executada).
          </p>
        ) : radarItens.length === 0 ? (
          <p className="text-sm text-muted">
            Nenhuma observação do radar para este recorte na referência{" "}
            {fmtDate(d.radar.referencia)}.
          </p>
        ) : (
          <ul className="space-y-2 text-sm">
            {radarItens.map((i) => (
              <li
                key={`${i.tipo}-${i.cd_ibge}-${i.categoria}-${i.periodo_inicio}`}
              >
                <strong>
                  {i.municipio ? `${i.municipio}: ` : ""}
                  {i.titulo}
                </strong>
                <p className="text-muted">{i.explicacao}</p>
              </li>
            ))}
          </ul>
        )}
      </Secao>

      <Secao n={9} titulo="Qualidade e completude dos dados">
        {!d.qual ? (
          <p className="text-sm text-muted">
            Indicadores de qualidade indisponíveis (etapa do pipeline não
            executada).
          </p>
        ) : (
          <ul className="list-disc space-y-1 pl-5 text-sm">
            <li>
              Dados até {fmtDate(d.meta.dados_ate)}; semanas completas até{" "}
              {fmtDate(d.meta.completo_ate)}.
              {parciais.length > 0 &&
                ` Semanas ainda incompletas: ${parciais
                  .map(
                    (s) =>
                      `${fmtDate(s.semana)} (${fmtNum((s.razao ?? 0) * 100, 0)}%)`,
                  )
                  .join(", ")}.`}
            </li>
            {qCat && (
              <li>
                Arquivo {anoQual}: {fmtNum(qCat.coord_valida_pct, 0)}% dos
                registros de {nome.toLowerCase()} com local utilizável e{" "}
                {fmtNum(qCat.sem_hora_pct, 0)}% sem hora.
              </li>
            )}
          </ul>
        )}
      </Secao>

      <Secao n={10} titulo="Metodologia">
        <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
          <li>
            Comparações usam meses completos (semana completa = total estadual ≥
            85% da mediana das 8 semanas anteriores).
          </li>
          <li>Taxas = registros ÷ população do Censo 2022 × 100 mil.</li>
          <li>
            Radar: critérios explícitos por tipo (CUSUM sobre o modelo de
            participação no total estadual, variação anual relativa ao estado,
            picos semanais). Avaliação retrospectiva na página Qualidade.
          </li>
          <li>
            Proteção: valores abaixo de {d.meta.k_min} suprimidos; contagens por
            hexágono arredondadas.
          </li>
        </ul>
      </Secao>

      <Secao n={11} titulo="Limitações">
        <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
          {disclaimers.map((x) => (
            <li key={x}>{x}</li>
          ))}
        </ul>
      </Secao>

      <Secao n={12} titulo="Fontes">
        <p className="text-sm text-muted">
          SSP-SP (SPDados, boletins de ocorrência, arquivos anuais) e IBGE
          (malha municipal e Censo 2022). Métodos em docs/analises.md,
          docs/mudancas.md e docs/previsao.md do repositório.
        </p>
      </Secao>
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
