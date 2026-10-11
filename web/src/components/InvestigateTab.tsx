"use client";

import {
  Badge,
  Delta,
  fmtDate,
  fmtInt,
  fmtNum,
  Notice,
  StateMessage,
} from "@/components/ui";
import { analysis, type Decomposicao, type Veredito } from "@/lib/api";
import { useLoad } from "@/lib/useLoad";

const VEREDITO: Record<
  Veredito,
  { rotulo: string; tom: "accent" | "warning" | "neutral" }
> = {
  consistente: { rotulo: "Conclusão consistente", tom: "accent" },
  parcialmente_consistente: {
    rotulo: "Parcialmente consistente",
    tom: "neutral",
  },
  sensivel_a_janela: { rotulo: "Sensível ao recorte", tom: "warning" },
  indistinguivel_do_ruido: {
    rotulo: "Indistinguível do ruído",
    tom: "warning",
  },
  insuficiente: { rotulo: "Dados insuficientes", tom: "neutral" },
};

function Contribuicoes({ d, titulo }: { d: Decomposicao; titulo: string }) {
  const maxAbs = Math.max(...d.itens.map((i) => Math.abs(i.variacao_abs)), 1);
  return (
    <section>
      <h3 className="text-sm font-semibold">{titulo}</h3>
      <p className="mt-0.5 text-xs text-muted">
        {fmtDate(d.inicio)}–{fmtDate(d.fim)} vs. {fmtDate(d.inicio_anterior)}–
        {fmtDate(d.fim_anterior)}: total {fmtInt(d.total_atual)} vs.{" "}
        {fmtInt(d.total_anterior)} (<Delta value={d.variacao_total_pct} />)
      </p>
      <ul className="mt-2 space-y-1.5 text-sm">
        {d.itens.map((i) => {
          const w = (100 * Math.abs(i.variacao_abs)) / maxAbs;
          return (
            <li key={i.chave}>
              <div className="flex items-baseline justify-between gap-2">
                <span className="truncate">{i.nome}</span>
                <span className="shrink-0 tabular-nums">
                  {i.variacao_abs > 0 ? "+" : ""}
                  {fmtInt(i.variacao_abs)}
                  <span className="ml-1 text-xs text-muted">
                    {i.contribuicao_pct != null
                      ? `(${fmtNum(i.contribuicao_pct)}% da variação)`
                      : ""}
                  </span>
                </span>
              </div>
              {/* barra divergente em cor neutra: o lado indica o sentido, o texto confirma */}
              <div
                className="relative mt-0.5 h-1.5 rounded bg-surface-2"
                aria-hidden="true"
              >
                <div
                  className="absolute top-0 h-1.5 rounded bg-foreground/50"
                  style={
                    i.variacao_abs >= 0
                      ? { left: "50%", width: `${w / 2}%` }
                      : { right: "50%", width: `${w / 2}%` }
                  }
                />
                <div className="absolute left-1/2 top-[-2px] h-2.5 w-px bg-muted" />
              </div>
            </li>
          );
        })}
      </ul>
      {d.nao_publicados > 0 && (
        <p className="mt-1 text-xs text-muted">
          {d.nao_publicados} item(ns) com menos de 5 registros em algum período
          ficam fora dos totais.
        </p>
      )}
    </section>
  );
}

export function InvestigateTab({
  categoria,
  nomeCategoria,
  cdIbge,
  municipio,
}: {
  categoria: string;
  nomeCategoria: string;
  cdIbge: number | null;
  municipio: string | null;
}) {
  const where = municipio ?? "Estado de São Paulo";
  const r = useLoad(
    () => analysis.robustez({ categoria, cd_ibge: cdIbge ?? undefined }),
    [categoria, cdIbge],
  );
  const porCat = useLoad(
    () =>
      analysis.decomposicao({ por: "categoria", cd_ibge: cdIbge ?? undefined }),
    [cdIbge],
  );
  const porMun = useLoad(
    () => analysis.decomposicao({ por: "municipio", categoria, top: 8 }),
    [categoria],
    cdIbge == null,
  );
  return (
    <div className="space-y-6">
      <p className="text-xs text-muted">
        Recorte: <strong className="text-foreground">{where}</strong>,{" "}
        {nomeCategoria.toLowerCase()}. Perguntas: a variação se sustenta? De
        onde ela vem?
      </p>

      <section>
        <h3 className="text-sm font-semibold">A conclusão se sustenta?</h3>
        <div className="mt-2">
          <StateMessage loading={r.loading} error={r.error} onRetry={r.retry}>
            {r.data && (
              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={VEREDITO[r.data.veredito].tom}>
                    {VEREDITO[r.data.veredito].rotulo}
                  </Badge>
                </div>
                <p className="text-sm">{r.data.resumo}</p>
                <table className="w-full text-xs">
                  <caption className="sr-only">
                    Verificações de robustez
                  </caption>
                  <tbody>
                    {r.data.verificacoes.map((v) => (
                      <tr
                        key={v.nome}
                        className="border-b border-border/60 align-top"
                      >
                        <th
                          scope="row"
                          className="py-1.5 pr-2 text-left font-normal text-muted"
                        >
                          {v.descricao}
                          <span className="block text-[11px]">{v.detalhe}</span>
                        </th>
                        <td className="whitespace-nowrap py-1.5 text-right">
                          <Delta
                            value={v.variacao_pct}
                            suffix={
                              v.nome === "relativo_ao_estado" ? " p.p." : "%"
                            }
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <ul className="list-disc space-y-0.5 pl-4 text-xs text-muted">
                  {r.data.cobertura.map((c) => (
                    <li key={c}>{c}</li>
                  ))}
                </ul>
              </div>
            )}
          </StateMessage>
        </div>
      </section>

      <StateMessage
        loading={porCat.loading}
        error={porCat.error}
        onRetry={porCat.retry}
      >
        {porCat.data && (
          <Contribuicoes
            d={porCat.data}
            titulo={`O que mudou no total de ${where}, por tipo de crime`}
          />
        )}
      </StateMessage>

      {cdIbge == null && (
        <StateMessage
          loading={porMun.loading}
          error={porMun.error}
          onRetry={porMun.retry}
        >
          {porMun.data && (
            <Contribuicoes
              d={porMun.data}
              titulo={`${nomeCategoria}: municípios que mais contribuíram para a variação do estado`}
            />
          )}
        </StateMessage>
      )}

      <Notice tone="info" title="Contribuição não é causa">
        A decomposição só mostra onde a variação se concentrou. Municípios
        grandes contribuem mais por terem mais registros; mudanças de registro e
        de policiamento também aparecem aqui.
      </Notice>
    </div>
  );
}
