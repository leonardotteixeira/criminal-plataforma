"use client";

import { useState } from "react";
import { AppHeader } from "@/components/AppHeader";
import {
  Badge,
  Card,
  fmtDate,
  fmtInt,
  fmtNum,
  Notice,
  selectClass,
  Stat,
  StateMessage,
} from "@/components/ui";
import { analysis, api } from "@/lib/api";
import { useLoad } from "@/lib/useLoad";

const NOMES: Record<string, string> = {
  roubo: "Roubo",
  furto: "Furto",
  homicidio: "Homicídio e tentativa",
  lesao_corporal: "Lesão corporal dolosa",
  sexual: "Crimes sexuais",
  drogas: "Drogas",
  armas: "Porte de arma",
  transito: "Trânsito",
};
const CENARIOS: Record<string, string> = {
  sem_mudanca: "Sem mudança (falso alarme)",
  alta_30: "Alta de 30%",
  alta_50: "Alta de 50%",
  queda_30: "Queda de 30%",
};

function Pct({
  v,
  alerta,
}: {
  v: number | null | undefined;
  alerta?: boolean;
}) {
  if (v == null) return <span className="text-muted">indisponível</span>;
  return (
    <span
      className={`tabular-nums ${alerta ? "rounded bg-warning-bg px-1" : ""}`}
    >
      {fmtNum(v)}%{alerta && <span className="sr-only"> (atenção)</span>}
    </span>
  );
}

export default function QualidadePage() {
  const q = useLoad(() => analysis.qualidade(), []);
  const m = useLoad(() => api.meta(), []);
  const mud = useLoad(() => analysis.mudancas(), []);
  const anos = q.data?.anos.map((a) => a.ano) ?? [];
  const [ano, setAno] = useState<number | null>(null);
  const anoSel = ano ?? anos.at(-1) ?? null;
  const bronze =
    q.data?.etapas.find((e) => e.etapa === "bronze")?.registros ?? 0;

  return (
    <div className="flex min-h-dvh flex-col">
      <AppHeader />
      <main className="mx-auto w-full max-w-6xl flex-1 space-y-6 px-4 py-6 sm:px-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Qualidade dos dados
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-muted">
            Quanto dá para confiar em cada análise: o que entra, o que fica de
            fora e por quê. Tudo calculado pelo pipeline; nada é recalculado ao
            abrir esta página.
          </p>
        </div>

        <StateMessage loading={q.loading} error={q.error} onRetry={q.retry}>
          {q.data && (
            <>
              <Card title="Versão dos dados">
                <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                  <Stat
                    label="Fonte (SSP) atualizada em"
                    value={fmtDate(m.data?.fonte_atualizada_em)}
                  />
                  <Stat
                    label="Processado em"
                    value={fmtDate(m.data?.processado_em)}
                  />
                  <Stat
                    label="Dados até"
                    value={fmtDate(m.data?.dados_ate)}
                    hint="última semana não residual"
                  />
                  <Stat
                    label="Completos até"
                    value={fmtDate(m.data?.completo_ate)}
                    hint="usado em tendências e alertas"
                  />
                </dl>
                <p className="mt-3 text-xs text-muted">
                  Proteção: valores abaixo de {m.data?.k_min ?? 5} são
                  suprimidos; contagens por hexágono são arredondadas para
                  múltiplos de {m.data?.arredondamento_celulas ?? 5}.
                </p>
              </Card>

              <Card
                title="Do arquivo ao painel"
                description="Registros em cada etapa e o motivo de cada redução."
              >
                <ol className="space-y-3">
                  {q.data.etapas.map((e) => {
                    const pct = bronze ? (100 * e.registros) / bronze : 0;
                    return (
                      <li key={e.etapa}>
                        <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
                          <span className="font-medium">{e.definicao}</span>
                          <span className="tabular-nums">
                            {fmtInt(e.registros)}{" "}
                            <span className="text-muted">({fmtNum(pct)}%)</span>
                          </span>
                        </div>
                        <div
                          className="mt-1 h-2 rounded bg-surface-2"
                          aria-hidden="true"
                        >
                          <div
                            className="h-2 rounded bg-accent"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </li>
                    );
                  })}
                </ol>
              </Card>

              <Card
                title="Completude das semanas recentes"
                description="Total estadual de cada semana em relação à mediana das 8 anteriores. Semanas parciais ficam fora de tendências e alertas."
              >
                <div
                  className="flex h-28 items-end gap-0.5"
                  role="img"
                  aria-label="Completude semanal das últimas 30 semanas"
                >
                  {[...q.data.semanas].reverse().map((s) => (
                    <div
                      key={s.semana}
                      className={`flex-1 rounded-t ${s.status === "completa" ? "bg-accent/70" : s.status === "parcial" ? "bg-warning" : "bg-danger"}`}
                      style={{
                        height: `${Math.min(100, (s.razao ?? 0) * 100)}%`,
                      }}
                      title={`Semana de ${fmtDate(s.semana)}: ${fmtInt(s.registros)} registros (${fmtNum((s.razao ?? 0) * 100, 0)}%), ${s.status}`}
                    />
                  ))}
                </div>
                <ul className="mt-3 space-y-1 text-sm">
                  {q.data.semanas
                    .filter((s) => s.status !== "completa")
                    .map((s) => (
                      <li key={s.semana}>
                        <Badge tone="warning">{s.status}</Badge> semana de{" "}
                        {fmtDate(s.semana)}: {fmtInt(s.registros)} registros (
                        {fmtNum((s.razao ?? 0) * 100, 0)}% do típico)
                      </li>
                    ))}
                </ul>
              </Card>

              <Card
                title="Por arquivo anual da SSP"
                description="Destacado: indicador que limita alguma análise."
              >
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[44rem] text-sm">
                    <caption className="sr-only">
                      Indicadores de qualidade por arquivo anual
                    </caption>
                    <thead>
                      <tr className="border-b border-border text-left text-xs text-muted">
                        <th scope="col" className="py-2">
                          Arquivo
                        </th>
                        <th scope="col" className="text-right">
                          Registros
                        </th>
                        <th scope="col" className="text-right">
                          Coord. válida
                        </th>
                        <th scope="col" className="text-right">
                          Coord. 0/ocultada
                        </th>
                        <th scope="col" className="text-right">
                          Sem hora
                        </th>
                        <th scope="col" className="text-right">
                          Sem tipo de local
                        </th>
                        <th scope="col" className="text-right">
                          Data imputada
                        </th>
                        <th scope="col" className="text-right">
                          Fora da janela
                        </th>
                        <th scope="col" className="text-right">
                          Tamanho
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {q.data.anos.map((a) => (
                        <tr key={a.ano} className="border-b border-border/60">
                          <th
                            scope="row"
                            className="py-2 text-left font-medium"
                          >
                            {a.ano}
                          </th>
                          <td className="text-right tabular-nums">
                            {fmtInt(a.registros)}
                          </td>
                          <td className="text-right">
                            <Pct
                              v={a.coord_valida_pct}
                              alerta={a.coord_valida_pct < 70}
                            />
                          </td>
                          <td className="text-right">
                            <Pct v={a.coord_zero_pct} />
                          </td>
                          <td className="text-right">
                            <Pct
                              v={a.sem_hora_pct}
                              alerta={a.sem_hora_pct > 30}
                            />
                          </td>
                          <td className="text-right">
                            <Pct
                              v={a.sem_tipo_local_pct}
                              alerta={a.sem_tipo_local_pct > 50}
                            />
                          </td>
                          <td className="text-right">
                            <Pct v={a.data_imputada_pct} />
                          </td>
                          <td className="text-right tabular-nums">
                            {fmtInt(a.fora_da_janela)}
                          </td>
                          <td className="text-right tabular-nums">
                            {a.tamanho_mb == null ? (
                              <span className="text-muted">indisponível</span>
                            ) : (
                              `${fmtNum(a.tamanho_mb, 0)} MB`
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="mt-2 text-xs text-muted">
                  “Sem tipo de local” em 100% indica que a coluna não existe no
                  arquivo daquele ano (mudança de layout da SSP), não que o
                  campo esteja vazio nos BOs.
                </p>
              </Card>

              <Card
                title="Cobertura por tipo de crime"
                description="Quanto do mapa e da grade de horários representa cada tipo."
                actions={
                  <label className="w-28 text-xs text-muted">
                    Arquivo
                    <select
                      className={selectClass}
                      value={anoSel ?? ""}
                      onChange={(e) => setAno(Number(e.target.value))}
                    >
                      {anos.map((a) => (
                        <option key={a} value={a}>
                          {a}
                        </option>
                      ))}
                    </select>
                  </label>
                }
              >
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[30rem] text-sm">
                    <caption className="sr-only">
                      Cobertura por categoria no arquivo selecionado
                    </caption>
                    <thead>
                      <tr className="border-b border-border text-left text-xs text-muted">
                        <th scope="col" className="py-2">
                          Tipo
                        </th>
                        <th scope="col" className="text-right">
                          Registros
                        </th>
                        <th scope="col" className="text-right">
                          No mapa (coord. válida)
                        </th>
                        <th scope="col" className="text-right">
                          Sem hora
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {q.data.categorias
                        .filter(
                          (c) => c.ano === anoSel && c.categoria !== "outros",
                        )
                        .map((c) => (
                          <tr
                            key={c.categoria}
                            className="border-b border-border/60"
                          >
                            <th
                              scope="row"
                              className="py-2 text-left font-medium"
                            >
                              {NOMES[c.categoria] ?? c.categoria}
                            </th>
                            <td className="text-right tabular-nums">
                              {fmtInt(c.registros)}
                            </td>
                            <td className="text-right">
                              <Pct
                                v={c.coord_valida_pct}
                                alerta={c.coord_valida_pct < 60}
                              />
                            </td>
                            <td className="text-right">
                              <Pct
                                v={c.sem_hora_pct}
                                alerta={c.sem_hora_pct > 40}
                              />
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
                <Notice tone="info" className="mt-3">
                  Crimes sexuais têm o local ocultado pela própria SSP: aparecem
                  em séries e taxas por município, nunca no mapa. Para tipos com
                  baixa cobertura, prefira as análises por município.
                </Notice>
              </Card>
            </>
          )}
        </StateMessage>

        <section id="mudancas" className="scroll-mt-4">
          <Card
            title="Avaliação do detector de mudanças persistentes"
            description="Usado no Radar. Só é exibido para tipos em que a avaliação sustenta o sinal."
          >
            <StateMessage
              loading={mud.loading}
              error={mud.error}
              onRetry={mud.retry}
            >
              {mud.data && (
                <div className="space-y-5">
                  <p className="text-sm text-muted">{mud.data.metodo}</p>
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[40rem] text-sm">
                      <caption className="mb-2 text-left text-sm font-medium">
                        Retrospectiva nos dados reais: o sinal se manteve nas 8
                        semanas seguintes?
                      </caption>
                      <thead>
                        <tr className="border-b border-border text-left text-xs text-muted">
                          <th scope="col" className="py-2">
                            Tipo
                          </th>
                          <th scope="col" className="text-right">
                            Séries avaliadas
                          </th>
                          <th scope="col" className="text-right">
                            Sinais
                          </th>
                          <th scope="col" className="text-right">
                            Confirmados
                          </th>
                          <th scope="col" className="text-right">
                            Por acaso
                          </th>
                          <th scope="col" className="text-right">
                            Referência simples
                          </th>
                          <th scope="col" className="text-right">
                            Usado no Radar
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {mud.data.avaliacao.map((a) => (
                          <tr
                            key={a.categoria}
                            className="border-b border-border/60"
                          >
                            <th
                              scope="row"
                              className="py-2 text-left font-medium"
                            >
                              {NOMES[a.categoria] ?? a.categoria}
                            </th>
                            <td className="text-right tabular-nums">
                              {fmtInt(a.series_avaliadas)}
                            </td>
                            <td className="text-right tabular-nums">
                              {fmtInt(a.sinais)}
                            </td>
                            <td className="text-right">
                              <Pct v={a.confirmados_pct} />
                            </td>
                            <td className="text-right">
                              <Pct v={a.confirmacao_acaso_pct} />
                            </td>
                            <td className="text-right tabular-nums">
                              {a.referencia_confirmados_pct == null
                                ? "—"
                                : `${fmtNum(a.referencia_confirmados_pct)}% (acaso ${fmtNum(a.referencia_confirmacao_acaso_pct)}%)`}
                            </td>
                            <td className="text-right">
                              {a.confiavel ? "Sim" : "Não"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[34rem] text-sm">
                      <caption className="mb-2 text-left text-sm font-medium">
                        Simulação com a forma real da série estadual de roubo
                        (taxa de sinal por janela de 12 semanas)
                      </caption>
                      <thead>
                        <tr className="border-b border-border text-left text-xs text-muted">
                          <th scope="col" className="py-2">
                            Registros/semana
                          </th>
                          <th scope="col">Cenário</th>
                          <th scope="col" className="text-right">
                            CUSUM
                          </th>
                          <th scope="col" className="text-right">
                            Referência
                          </th>
                          <th scope="col" className="text-right">
                            Atraso médio
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {mud.data.simulacao.map((s) => (
                          <tr
                            key={`${s.nivel_semanal}-${s.cenario}`}
                            className="border-b border-border/60"
                          >
                            <td className="py-1.5 tabular-nums">
                              {fmtNum(s.nivel_semanal, 0)}
                            </td>
                            <td>{CENARIOS[s.cenario] ?? s.cenario}</td>
                            <td className="text-right tabular-nums">
                              {fmtNum(s.cusum_taxa_sinal * 100)}%
                            </td>
                            <td className="text-right tabular-nums">
                              {fmtNum(s.referencia_taxa_sinal * 100)}%
                            </td>
                            <td className="text-right tabular-nums">
                              {s.cusum_atraso_medio_semanas == null
                                ? "—"
                                : `${fmtNum(s.cusum_atraso_medio_semanas)} sem.`}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <Notice tone="warning" title="Como interpretar">
                    Em séries pequenas (≈3 registros/semana) o detector quase
                    nunca encontra mudanças, mesmo reais: ausência de sinal não
                    é evidência de estabilidade. A referência simples confirma
                    em proporção parecida; o CUSUM acrescenta estimativa de
                    início e magnitude e desconta movimentos do estado inteiro.
                  </Notice>
                </div>
              )}
            </StateMessage>
          </Card>
        </section>

        {q.data && (
          <Card title="Histórico de execuções do pipeline">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[36rem] text-sm">
                <caption className="sr-only">
                  Execuções recentes do pipeline
                </caption>
                <thead>
                  <tr className="border-b border-border text-left text-xs text-muted">
                    <th scope="col" className="py-2">
                      Processado em
                    </th>
                    <th scope="col">Etapas</th>
                    <th scope="col">Fonte</th>
                    <th scope="col">Dados até</th>
                    <th scope="col" className="text-right">
                      Registros
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {q.data.execucoes.map((e) => (
                    <tr
                      key={e.processado_em}
                      className="border-b border-border/60"
                    >
                      <td className="py-1.5">
                        {e.processado_em.replace("T", " ").slice(0, 16)}
                      </td>
                      <td>{e.etapas}</td>
                      <td>{fmtDate(e.fonte_atualizada_em)}</td>
                      <td>{fmtDate(e.dados_ate)}</td>
                      <td className="text-right tabular-nums">
                        {fmtInt(e.registros_silver)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <dl className="mt-4 space-y-1 text-xs text-muted">
              {Object.entries(q.data.definicoes).map(([k, v]) => (
                <div key={k}>
                  <dt className="inline font-medium text-foreground">{k}: </dt>
                  <dd className="inline">{v}</dd>
                </div>
              ))}
            </dl>
          </Card>
        )}
      </main>
    </div>
  );
}
