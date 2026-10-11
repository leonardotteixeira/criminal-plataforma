"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { AppHeader } from "@/components/AppHeader";
import { MultiLineChart } from "@/components/Charts";
import { MunicipioPicker } from "@/components/MunicipioPicker";
import { SaveViewButton } from "@/components/SavedViews";
import {
  buttonClass,
  Card,
  Delta,
  fmtDate,
  fmtInt,
  fmtNum,
  Notice,
  selectClass,
  StateMessage,
} from "@/components/ui";
import {
  analysis,
  api,
  municipiosLista,
  type Categoria,
  type Meta,
  type MunicipioRef,
  type Perfil,
} from "@/lib/api";
import { downloadText, toCsv } from "@/lib/csv";
import { useLoad } from "@/lib/useLoad";

const MAX = 4;
const PERIODOS = [6, 12, 24];

function exportar(p: Perfil, nomes: Record<string, string>, kMin: number) {
  const rows = p.municipios.flatMap((m) =>
    m.categorias.map((c) => [
      m.cd_ibge,
      m.municipio,
      m.populacao_2022,
      nomes[c.categoria] ?? c.categoria,
      c.n,
      c.n_anterior,
      c.taxa_100k,
      c.variacao_pct,
      c.participacao_pct,
    ]),
  );
  const csv = toCsv(
    [
      "cd_ibge",
      "municipio",
      "populacao_2022",
      "categoria",
      "registros",
      "registros_periodo_anterior",
      "taxa_100k",
      "variacao_pct",
      "participacao_pct",
    ],
    rows,
    [
      `Comparação de municípios: ${p.inicio} a ${p.fim} vs. ${p.inicio_anterior} a ${p.fim_anterior}`,
      `Fonte: SSP-SP e IBGE (Censo 2022). Valores < ${kMin} suprimidos (vazios). Registros, não crimes reais.`,
    ],
  );
  downloadText(`sinalbr_comparacao_${p.inicio}_${p.fim}.csv`, csv);
}

function CompararInner() {
  const sp = useSearchParams();
  const router = useRouter();
  const path = usePathname();
  const [ids, setIds] = useState<number[]>(
    (sp.get("m") ?? "")
      .split(",")
      .map(Number)
      .filter((n) => Number.isInteger(n) && n > 0)
      .slice(0, MAX),
  );
  const [meses, setMeses] = useState(
    PERIODOS.includes(Number(sp.get("meses"))) ? Number(sp.get("meses")) : 12,
  );
  const [categoria, setCategoria] = useState(sp.get("categoria") ?? "roubo");
  const [cats, setCats] = useState<Categoria[]>([]);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [lista, setLista] = useState<MunicipioRef[]>([]);

  useEffect(() => {
    api
      .categorias()
      .then(setCats)
      .catch(() => setCats([]));
    api
      .meta()
      .then(setMeta)
      .catch(() => setMeta(null));
    municipiosLista()
      .then(setLista)
      .catch(() => setLista([]));
  }, []);

  useEffect(() => {
    const p = new URLSearchParams();
    if (ids.length) p.set("m", ids.join(","));
    p.set("meses", String(meses));
    p.set("categoria", categoria);
    router.replace(`${path}?${p}`, { scroll: false });
  }, [ids, meses, categoria, path, router]);

  const nomes = useMemo(
    () => Object.fromEntries(cats.map((c) => [c.id, c.nome])),
    [cats],
  );
  const nomeMun = (cd: number) =>
    lista.find((m) => m.cd_ibge === cd)?.municipio ?? String(cd);

  const perfil = useLoad(
    () => analysis.perfil({ cd_ibge: ids, meses }),
    [ids, meses],
    ids.length > 0,
  );
  const serie = useLoad(
    () =>
      analysis.regioes({
        cd_ibge: ids,
        categoria,
        inicio: perfil.data!.inicio,
        fim: perfil.data!.fim,
      }),
    [ids, categoria, perfil.data?.inicio, perfil.data?.fim],
    ids.length > 0 && !!perfil.data,
  );

  const p = perfil.data;
  const razoes = p?.razoes.filter((r) => r.categoria === categoria) ?? [];
  const titulo = `Comparação: ${ids.map(nomeMun).join(" × ")} (${nomes[categoria] ?? categoria}, ${meses} meses)`;

  return (
    <div className="flex min-h-dvh flex-col">
      <AppHeader
        actions={
          ids.length > 0 && (
            <SaveViewButton titulo={titulo} dadosAte={meta?.dados_ate} />
          )
        }
      />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6">
        <h1 className="text-2xl font-semibold tracking-tight">
          Comparar municípios
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-muted">
          Até {MAX} municípios lado a lado, sempre em meses completos e com
          taxas por 100 mil habitantes. O primeiro é a referência das razões.
        </p>

        <Card className="mt-5">
          <div className="flex flex-wrap items-end gap-3">
            <ul
              className="flex flex-wrap gap-2"
              aria-label="Municípios selecionados"
            >
              {ids.map((cd, i) => (
                <li
                  key={cd}
                  className="inline-flex items-center gap-1 rounded-full border border-border bg-surface-2 py-1 pl-3 pr-1 text-sm"
                >
                  {i === 0 && <span className="text-xs text-muted">ref.</span>}
                  {nomeMun(cd)}
                  {i > 0 && (
                    <button
                      type="button"
                      className="rounded-full px-1.5 text-xs text-muted hover:text-foreground"
                      onClick={() =>
                        setIds([cd, ...ids.filter((x) => x !== cd)])
                      }
                      aria-label={`Usar ${nomeMun(cd)} como referência`}
                      title="Usar como referência"
                    >
                      ⇤
                    </button>
                  )}
                  <button
                    type="button"
                    className="rounded-full px-1.5 text-muted hover:text-foreground"
                    onClick={() => setIds(ids.filter((x) => x !== cd))}
                    aria-label={`Remover ${nomeMun(cd)}`}
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
            {ids.length < MAX && (
              <div className="w-60">
                <MunicipioPicker
                  label="Adicionar município"
                  value={null}
                  placeholder="Digite o nome…"
                  allowClear={false}
                  exclude={ids}
                  onChange={(m) => m && setIds([...ids, m.cd_ibge])}
                />
              </div>
            )}
            <label className="w-40 text-xs text-muted">
              Tipo de crime (gráfico e razões)
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
            <label className="w-32 text-xs text-muted">
              Período
              <select
                className={selectClass}
                value={meses}
                onChange={(e) => setMeses(Number(e.target.value))}
              >
                {PERIODOS.map((m) => (
                  <option key={m} value={m}>
                    {m} meses
                  </option>
                ))}
              </select>
            </label>
            {p && (
              <button
                type="button"
                className={`${buttonClass} ml-auto`}
                onClick={() => exportar(p, nomes, meta?.k_min ?? 5)}
              >
                Exportar CSV
              </button>
            )}
          </div>
        </Card>

        {ids.length === 0 ? (
          <div className="mt-6 rounded-xl border border-dashed border-border p-6 text-sm text-muted">
            <p>Adicione ao menos um município para começar.</p>
            <button
              type="button"
              className={`${buttonClass} mt-3`}
              onClick={() => setIds([3550308, 3509502])}
            >
              Exemplo: São Paulo × Campinas
            </button>
          </div>
        ) : (
          <div className="mt-6 space-y-6">
            <StateMessage
              loading={perfil.loading}
              error={perfil.error}
              onRetry={perfil.retry}
            >
              {p && (
                <>
                  <p className="text-sm text-muted">
                    Período:{" "}
                    <strong className="text-foreground">
                      {fmtDate(p.inicio)}
                    </strong>{" "}
                    a{" "}
                    <strong className="text-foreground">
                      {fmtDate(p.fim)}
                    </strong>
                    , comparado com {fmtDate(p.inicio_anterior)} a{" "}
                    {fmtDate(p.fim_anterior)}.
                  </p>

                  <Card
                    title={`${nomes[categoria] ?? categoria}: resumo`}
                    description="Contagem absoluta e taxa por 100 mil habitantes não são a mesma coisa: municípios maiores registram mais."
                  >
                    <div className="overflow-x-auto">
                      <table className="w-full min-w-[34rem] text-sm">
                        <caption className="sr-only">
                          Resumo por município
                        </caption>
                        <thead>
                          <tr className="border-b border-border text-left text-xs text-muted">
                            <th scope="col" className="py-2">
                              Município
                            </th>
                            <th scope="col" className="text-right">
                              População
                            </th>
                            <th scope="col" className="text-right">
                              Registros
                            </th>
                            <th scope="col" className="text-right">
                              Taxa/100 mil
                            </th>
                            <th scope="col" className="text-right">
                              vs. período anterior
                            </th>
                            <th scope="col" className="text-right">
                              Todos os crimes /100 mil
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {p.municipios.map((m) => {
                            const c = m.categorias.find(
                              (x) => x.categoria === categoria,
                            );
                            return (
                              <tr
                                key={m.cd_ibge}
                                className="border-b border-border/60"
                              >
                                <th
                                  scope="row"
                                  className="py-2 text-left font-medium"
                                >
                                  {m.municipio}
                                </th>
                                <td className="text-right tabular-nums">
                                  {fmtInt(m.populacao_2022)}
                                </td>
                                <td className="text-right tabular-nums">
                                  {fmtInt(c?.n)}
                                </td>
                                <td className="text-right tabular-nums">
                                  {fmtNum(c?.taxa_100k)}
                                </td>
                                <td className="text-right">
                                  <Delta value={c?.variacao_pct} />
                                </td>
                                <td className="text-right tabular-nums">
                                  {fmtNum(m.taxa_total_100k)}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                    <p className="mt-2 text-xs text-muted">
                      — = menos de {meta?.k_min ?? 5} registros (suprimido).
                    </p>
                  </Card>

                  <Card
                    title="Evolução mensal da taxa"
                    description={`${nomes[categoria] ?? categoria}, registros por 100 mil habitantes por mês.`}
                  >
                    <StateMessage
                      loading={serie.loading}
                      error={serie.error}
                      onRetry={serie.retry}
                    >
                      {serie.data && (
                        <MultiLineChart
                          label={`Taxa mensal de ${nomes[categoria] ?? categoria} por município`}
                          unit="por 100 mil hab./mês"
                          width={720}
                          height={220}
                          series={serie.data
                            .filter((s) => s.serie_taxa_100k.length > 1)
                            .map((s) => ({
                              name: s.municipio,
                              points: s.serie_taxa_100k.map(([x, y]) => ({
                                x,
                                y,
                              })),
                            }))}
                        />
                      )}
                      {serie.data?.some(
                        (s) => s.serie_taxa_100k.length <= 1,
                      ) && (
                        <p className="mt-2 text-xs text-muted">
                          Sem série para{" "}
                          {serie.data
                            .filter((s) => s.serie_taxa_100k.length <= 1)
                            .map((s) => s.municipio)
                            .join(", ")}
                          : meses com menos de {meta?.k_min ?? 5} registros são
                          suprimidos.
                        </p>
                      )}
                    </StateMessage>
                  </Card>

                  {ids.length > 1 && (
                    <Card
                      title="Diferença em relação à referência"
                      description={`Razão entre taxas de ${nomes[categoria] ?? categoria}: 1,0 = mesma taxa. Intervalo de 95% aproximado.`}
                    >
                      {razoes.length === 0 ? (
                        <p className="text-sm text-muted">
                          Sem razão calculável: algum município tem menos de{" "}
                          {meta?.k_min ?? 5} registros.
                        </p>
                      ) : (
                        <ul className="space-y-2 text-sm">
                          {razoes.map((r) => (
                            <li
                              key={r.cd_ibge}
                              className="rounded-lg border border-border bg-background p-3"
                            >
                              <p>
                                <strong>{nomeMun(r.cd_ibge)}</strong> vs.{" "}
                                {nomeMun(r.cd_ibge_ref)}: razão{" "}
                                <strong className="tabular-nums">
                                  {fmtNum(r.razao, 2)}
                                </strong>{" "}
                                <span className="text-muted tabular-nums">
                                  (IC 95%: {fmtNum(r.ic_inf, 2)} a{" "}
                                  {fmtNum(r.ic_sup, 2)})
                                </span>
                              </p>
                              <p className="text-muted">{r.leitura}.</p>
                            </li>
                          ))}
                        </ul>
                      )}
                      <p className="mt-3 text-xs text-muted">{p.nota}</p>
                    </Card>
                  )}

                  <Card
                    title="Distribuição por tipo de crime"
                    description="Taxa por 100 mil hab. e participação no total de registros de cada município."
                  >
                    <div className="overflow-x-auto">
                      <table className="w-full min-w-[34rem] text-sm">
                        <caption className="sr-only">
                          Taxa e participação por categoria
                        </caption>
                        <thead>
                          <tr className="border-b border-border text-left text-xs text-muted">
                            <th scope="col" className="py-2">
                              Tipo
                            </th>
                            {p.municipios.map((m) => (
                              <th
                                key={m.cd_ibge}
                                scope="col"
                                className="text-right"
                              >
                                {m.municipio}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {cats.map((c) => (
                            <tr
                              key={c.id}
                              className={`border-b border-border/60 ${c.id === categoria ? "bg-surface-2" : ""}`}
                            >
                              <th
                                scope="row"
                                className="py-2 text-left font-medium"
                              >
                                {c.nome}
                              </th>
                              {p.municipios.map((m) => {
                                const x = m.categorias.find(
                                  (y) => y.categoria === c.id,
                                );
                                return (
                                  <td
                                    key={m.cd_ibge}
                                    className="text-right tabular-nums"
                                  >
                                    {fmtNum(x?.taxa_100k)}
                                    <span className="ml-1 text-xs text-muted">
                                      {x?.participacao_pct != null
                                        ? `(${fmtNum(x.participacao_pct)}%)`
                                        : ""}
                                    </span>
                                  </td>
                                );
                              })}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </Card>

                  <Notice tone="warning" title="Antes de concluir">
                    Diferenças entre municípios refletem também subnotificação,
                    presença policial, delegacias de referência regional e
                    práticas de registro. Elas não indicam que um lugar seja
                    intrinsecamente mais perigoso nem explicam causas.
                  </Notice>
                </>
              )}
            </StateMessage>
          </div>
        )}
      </main>
    </div>
  );
}

export default function CompararPage() {
  return (
    <Suspense fallback={<p className="p-6">Carregando…</p>}>
      <CompararInner />
    </Suspense>
  );
}
