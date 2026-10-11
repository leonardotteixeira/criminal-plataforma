"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { AppHeader } from "@/components/AppHeader";
import { MunicipioPicker } from "@/components/MunicipioPicker";
import { SavedNote, SavedViewsList } from "@/components/SavedViews";
import { HistoryLine, SignalGlossary } from "@/components/Signals";
import {
  Badge,
  Card,
  fmtDate,
  fmtInt,
  Notice,
  selectClass,
  StateMessage,
  TextLink,
} from "@/components/ui";
import {
  analysis,
  api,
  type Categoria,
  type Meta,
  type RadarItem,
  type RadarTipo,
} from "@/lib/api";
import { useLoad } from "@/lib/useLoad";

const TIPOS: {
  id: RadarTipo;
  titulo: string;
  descricao: string;
  vazio: string;
}[] = [
  {
    id: "mudanca_persistente",
    titulo: "Mudanças persistentes",
    descricao:
      "Municípios que passaram a registrar, de forma sustentada, mais ou menos do que o padrão estadual explicaria.",
    vazio:
      "Nenhuma mudança persistente que passe nos critérios. Isso não significa estabilidade: séries pequenas não têm poder para detectar mudanças.",
  },
  {
    id: "variacao",
    titulo: "Variações anuais fora do padrão do estado",
    descricao:
      "Últimos 12 meses completos contra os 12 anteriores, quando a variação do município se afasta muito da do estado.",
    vazio:
      "Nenhuma variação anual se afasta o suficiente da variação estadual.",
  },
  {
    id: "anomalia",
    titulo: "Picos semanais",
    descricao:
      "Semanas com muito mais registros que o habitual. Picos isolados costumam vir de eventos de massa ou lotes de registro.",
    vazio: "Nenhum pico semanal nas últimas 4 semanas completas.",
  },
  {
    id: "dados",
    titulo: "Avisos sobre os dados",
    descricao: "Situações da base que afetam a leitura das análises.",
    vazio: "Nenhum aviso de dados para este recorte.",
  },
];

const ROTULO: Record<RadarTipo, string> = {
  mudanca_persistente: "Mudança persistente",
  variacao: "Variação anual",
  anomalia: "Pico semanal",
  dados: "Dados",
};

function itemLink(i: RadarItem): { href: string; label: string } {
  if (i.tipo === "dados")
    return { href: "/qualidade", label: "Ver qualidade dos dados" };
  const p = new URLSearchParams();
  if (i.categoria) p.set("categoria", i.categoria);
  if (i.cd_ibge) p.set("municipio", String(i.cd_ibge));
  p.set("aba", i.tipo === "anomalia" ? "alertas" : "tempo");
  return { href: `/dashboard?${p}`, label: "Investigar no painel" };
}

function Item({ i }: { i: RadarItem }) {
  const link = itemLink(i);
  return (
    <li className="rounded-lg border border-border bg-background p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={i.tipo === "dados" ? "warning" : "accent"}>
          {ROTULO[i.tipo]}
        </Badge>
        {i.direcao && (
          <span className="text-xs text-muted">
            <span aria-hidden="true">{i.direcao === "alta" ? "▲ " : "▼ "}</span>
            {i.direcao === "alta" ? "mais registros" : "menos registros"}
          </span>
        )}
        <span className="ml-auto text-xs text-muted">
          {fmtDate(i.periodo_inicio)} a {fmtDate(i.periodo_fim)}
        </span>
      </div>
      <h3 className="mt-1.5 font-semibold">
        {i.municipio ? `${i.municipio} · ` : ""}
        {i.titulo}
      </h3>
      <p className="mt-1 text-sm text-muted">{i.explicacao}</p>
      {i.historico && <HistoryLine h={i.historico} />}
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
        <TextLink href={link.href}>{link.label} →</TextLink>
        {i.cd_ibge && (
          <TextLink href={`/comparar?m=${i.cd_ibge}`}>
            Comparar com outros municípios
          </TextLink>
        )}
      </div>
    </li>
  );
}

function RadarInner() {
  const sp = useSearchParams();
  const router = useRouter();
  const path = usePathname();
  const [categoria, setCategoria] = useState(sp.get("categoria") ?? "");
  const [municipio, setMunicipio] = useState<number | null>(
    Number(sp.get("municipio")) || null,
  );
  const [porTipo, setPorTipo] = useState(6);
  const [cats, setCats] = useState<Categoria[]>([]);
  const [meta, setMeta] = useState<Meta | null>(null);

  useEffect(() => {
    api
      .categorias()
      .then(setCats)
      .catch(() => setCats([]));
    api
      .meta()
      .then(setMeta)
      .catch(() => setMeta(null));
  }, []);

  useEffect(() => {
    const p = new URLSearchParams();
    if (categoria) p.set("categoria", categoria);
    if (municipio) p.set("municipio", String(municipio));
    router.replace(`${path}${p.size ? `?${p}` : ""}`, { scroll: false });
  }, [categoria, municipio, path, router]);

  const r = useLoad(
    () =>
      analysis.radar({
        categoria: categoria || undefined,
        cd_ibge: municipio ?? undefined,
        por_tipo: porTipo,
      }),
    [categoria, municipio, porTipo],
  );

  return (
    <div className="flex min-h-dvh flex-col">
      <AppHeader />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              Radar territorial
            </h1>
            <p className="mt-1 max-w-2xl text-sm text-muted">
              Observações estatísticas que merecem investigação, com o critério
              de cada uma. Ponto de partida, não conclusão.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <label className="w-44 text-xs text-muted">
              Tipo de crime
              <select
                className={selectClass}
                value={categoria}
                onChange={(e) => setCategoria(e.target.value)}
              >
                <option value="">Todos</option>
                {cats.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nome}
                  </option>
                ))}
              </select>
            </label>
            <div className="w-56">
              <MunicipioPicker
                label="Município"
                value={municipio}
                onChange={(m) => setMunicipio(m?.cd_ibge ?? null)}
              />
            </div>
          </div>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
          <div className="space-y-6">
            <StateMessage loading={r.loading} error={r.error} onRetry={r.retry}>
              {r.data && (
                <>
                  <Notice tone="warning" title="Como ler">
                    {r.data.aviso} Referência: semanas completas até{" "}
                    {fmtDate(r.data.referencia)}.
                  </Notice>
                  {TIPOS.map((t) => {
                    const itens = r.data!.itens.filter((i) => i.tipo === t.id);
                    const total = r.data!.contagem[t.id] ?? 0;
                    return (
                      <Card
                        key={t.id}
                        title={
                          <>
                            {t.titulo}{" "}
                            <span className="font-normal text-muted">
                              ({fmtInt(total)})
                            </span>
                          </>
                        }
                        description={t.descricao}
                      >
                        {itens.length === 0 ? (
                          <p className="rounded-lg border border-dashed border-border p-3 text-sm text-muted">
                            {t.vazio}
                          </p>
                        ) : (
                          <ul className="space-y-2">
                            {itens.map((i) => (
                              <Item
                                key={`${i.tipo}-${i.cd_ibge}-${i.categoria}-${i.periodo_inicio}`}
                                i={i}
                              />
                            ))}
                          </ul>
                        )}
                        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
                          <details>
                            <summary className="cursor-pointer">
                              Critério de seleção
                            </summary>
                            <p className="mt-1 max-w-prose">
                              {r.data!.criterios[t.id]}
                            </p>
                          </details>
                          {total > itens.length && (
                            <button
                              type="button"
                              className="font-medium text-accent hover:underline"
                              onClick={() => setPorTipo(30)}
                            >
                              Mostrar mais ({Math.min(total, 30) - itens.length}
                              )
                            </button>
                          )}
                        </div>
                      </Card>
                    );
                  })}
                  <Card
                    title={
                      <>
                        Deixaram de ser detectados{" "}
                        <span className="font-normal text-muted">
                          ({fmtInt(r.data.deixaram_de_ser_detectados.length)})
                        </span>
                      </>
                    }
                    description="Mudanças persistentes presentes na avaliação anterior (4 semanas antes) e não na atual, com a série ainda avaliável."
                  >
                    {!r.data.historico_disponivel ? (
                      <p className="text-sm text-muted">
                        Histórico ainda não gerado (etapa “history” do
                        pipeline).
                      </p>
                    ) : r.data.deixaram_de_ser_detectados.length === 0 ? (
                      <p className="rounded-lg border border-dashed border-border p-3 text-sm text-muted">
                        Nenhuma mudança deixou de ser detectada desde a
                        avaliação anterior.
                      </p>
                    ) : (
                      <ul className="divide-y divide-border text-sm">
                        {r.data.deixaram_de_ser_detectados.map((e) => (
                          <li
                            key={`${e.cd_ibge}-${e.categoria}-${e.direcao}`}
                            className="flex flex-wrap justify-between gap-2 py-1.5"
                          >
                            <span>
                              <strong>{e.municipio}</strong> ·{" "}
                              {e.categoria_nome ?? e.categoria}
                              {e.direcao &&
                                ` (${e.direcao === "alta" ? "mais" : "menos"} registros)`}
                            </span>
                            <span className="text-xs text-muted">
                              última detecção {fmtDate(e.ultima_deteccao)} ·{" "}
                              {e.deteccoes} avaliação(ões)
                            </span>
                          </li>
                        ))}
                      </ul>
                    )}
                    <p className="mt-3 text-xs text-muted">
                      Deixar de ser detectado significa que o critério
                      estatístico deixou de ser atendido, não que a situação foi
                      resolvida. Histórico reconstruído com os dados atuais.
                    </p>
                  </Card>
                </>
              )}
            </StateMessage>
          </div>

          <aside className="space-y-6">
            <Card title="Suas análises salvas">
              <SavedViewsList dadosAte={meta?.dados_ate} />
              <div className="mt-3">
                <SavedNote />
              </div>
            </Card>
            <Card title="Como diferenciar os sinais">
              <SignalGlossary />
            </Card>
          </aside>
        </div>
      </main>
    </div>
  );
}

export default function RadarPage() {
  return (
    <Suspense fallback={<p className="p-6">Carregando…</p>}>
      <RadarInner />
    </Suspense>
  );
}
