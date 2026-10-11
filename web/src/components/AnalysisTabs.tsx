"use client";

import { useEffect, useState } from "react";
import { yearOverYearWindows } from "@/lib/dates";
import { HourDowGrid, LineChart, SeasonBars } from "@/components/Charts";
import {
  analysis,
  forecast,
  type Backtest,
  type Previsao,
  type Anomalias,
  type ComparacaoPeriodos,
  type HourDow,
  type Tendencia,
} from "@/lib/api";

type Props = {
  categoria: string;
  cdIbge: number | null;
  municipio: string | null;
  completoAte: string;
};

function pct(v: number | null | undefined) {
  if (v == null) return "—";
  return `${v > 0 ? "+" : ""}${v.toLocaleString("pt-BR")}%`;
}

function useLoad<T>(fn: () => Promise<T>, deps: unknown[]) {
  const key = JSON.stringify(deps);
  const [state, setState] = useState<{ key: string; data?: T; error?: string }>(
    { key: "" },
  );
  useEffect(() => {
    let live = true;
    fn()
      .then((data) => live && setState({ key, data }))
      .catch((e) => live && setState({ key, error: String(e.message ?? e) }));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return {
    data: state.key === key ? state.data : undefined,
    error: state.key === key ? state.error : undefined,
  };
}

export function TimeTab({ categoria, cdIbge, municipio }: Props) {
  const t = useLoad<Tendencia>(
    () => analysis.tendencia({ categoria, cd_ibge: cdIbge ?? undefined }),
    [categoria, cdIbge],
  );
  const h = useLoad<HourDow[]>(
    () => analysis.horaDia({ categoria, cd_ibge: cdIbge ?? undefined }),
    [categoria, cdIbge],
  );
  const where = municipio ?? "Estado de São Paulo";
  if (t.error)
    return (
      <p role="alert" className="text-sm text-red-600 dark:text-red-400">
        {t.error}
      </p>
    );
  return (
    <div className="space-y-5">
      <p className="text-xs text-muted">
        Recorte: <strong className="text-foreground">{where}</strong>. Clique em
        um município no ranking para filtrar.
      </p>
      {!t.data ? (
        <p className="text-sm text-muted">Carregando…</p>
      ) : t.data.suprimido ? (
        <p className="text-sm text-muted">
          Poucas ocorrências neste recorte: série oculta para proteger a
          privacidade.
        </p>
      ) : (
        <>
          <section>
            <h3 className="mb-1 text-sm font-semibold">Ocorrências por mês</h3>
            <LineChart
              data={t.data.serie}
              label={`Série mensal de ocorrências — ${where}`}
            />
            <dl className="mt-2 grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-xs text-muted">
                  Últimos 12 meses vs. 12 anteriores
                </dt>
                <dd className="text-lg font-semibold tabular-nums">
                  {pct(t.data.variacao_12m_pct)}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted">
                  Inclinação (últimos 24 meses)
                </dt>
                <dd className="text-lg font-semibold tabular-nums">
                  {pct(t.data.inclinacao_pct_ano)} /ano
                </dd>
              </div>
            </dl>
          </section>
          <section>
            <h3 className="mb-1 text-sm font-semibold">Sazonalidade</h3>
            <SeasonBars data={t.data.sazonalidade} />
          </section>
        </>
      )}
      <section>
        <h3 className="mb-1 text-sm font-semibold">Dia da semana × hora</h3>
        {h.data ? (
          <HourDowGrid data={h.data} />
        ) : (
          <p className="text-sm text-muted">Carregando…</p>
        )}
        <p className="mt-1 text-xs text-muted">
          Cerca de 30% dos BOs não informam a hora; o padrão vale só para os que
          informam.
        </p>
      </section>
      {t.data && (
        <p className="text-xs text-muted">
          {t.data.nota} Dados completos até{" "}
          {new Date(t.data.completo_ate + "T00:00:00").toLocaleDateString(
            "pt-BR",
          )}
          .
        </p>
      )}
    </div>
  );
}

export function CompareBox({ categoria, cdIbge, completoAte }: Props) {
  const { iniA, fimA, iniB, fimB } = yearOverYearWindows(completoAte);
  const c = useLoad<ComparacaoPeriodos>(
    () =>
      analysis.comparar({
        categoria,
        cd_ibge: cdIbge ?? undefined,
        inicio_a: iniA,
        fim_a: fimA,
        inicio_b: iniB,
        fim_b: fimB,
      }),
    [categoria, cdIbge, completoAte],
  );
  if (!c.data) return null;
  return (
    <p className="mt-3 rounded-md border border-border p-2 text-sm">
      {c.data.suprimido ? (
        "Comparação anual oculta (poucas ocorrências)."
      ) : (
        <>
          12 meses até{" "}
          {new Date(fimB + "T00:00:00").toLocaleDateString("pt-BR", {
            month: "short",
            year: "numeric",
          })}{" "}
          vs. 12 anteriores:{" "}
          <strong className="tabular-nums">{pct(c.data.variacao_pct)}</strong>{" "}
          <span className="text-muted">
            ({c.data.b?.toLocaleString("pt-BR")} vs.{" "}
            {c.data.a?.toLocaleString("pt-BR")})
          </span>
        </>
      )}
    </p>
  );
}

export function AlertsTab({ categoria }: Props) {
  const a = useLoad<Anomalias>(
    () => analysis.anomalias({ categoria, limit: 15 }),
    [categoria],
  );
  if (a.error)
    return (
      <p role="alert" className="text-sm text-red-600 dark:text-red-400">
        {a.error}
      </p>
    );
  if (!a.data) return <p className="text-sm text-muted">Carregando…</p>;
  return (
    <div>
      <h3 className="text-sm font-semibold">
        Aumentos incomuns recentes (por município)
      </h3>
      {a.data.itens.length === 0 ? (
        <p className="mt-2 text-sm text-muted">
          Nenhum aumento incomum nas últimas 8 semanas completas.
        </p>
      ) : (
        <ul className="mt-2 space-y-2 text-sm">
          {a.data.itens.map((i) => (
            <li
              key={`${i.id}-${i.semana}`}
              className="rounded border border-border p-2"
            >
              <div className="flex justify-between gap-2">
                <strong>{i.nome ?? i.id}</strong>
                <span className="text-xs text-muted">
                  sem. de{" "}
                  {new Date(i.semana + "T00:00:00").toLocaleDateString("pt-BR")}
                </span>
              </div>
              <div className="tabular-nums text-muted">
                {i.n.toLocaleString("pt-BR")} registros vs. ~
                {i.esperado.toLocaleString("pt-BR")} esperados (
                {i.razao.toLocaleString("pt-BR")}×)
              </div>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-xs text-muted">{a.data.metodo}</p>
    </div>
  );
}

export const CATS_PREVISAO = ["roubo", "furto", "lesao_corporal"];

const NOMES_MODELO: Record<string, string> = {
  persistencia: "Persistência (últimas 4 sem.)",
  media12: "Média de 12 semanas",
  sazonal: "Mesma época do ano anterior",
  glm: "Poisson (histórico)",
  glm_viz: "Poisson + vizinhança",
};

export function ForecastTab({
  categoria,
  previsao,
}: {
  categoria: string;
  previsao: Previsao | null;
}) {
  const ok = CATS_PREVISAO.includes(categoria);
  const b = useLoad<Backtest>(
    () =>
      ok ? forecast.backtest(categoria) : Promise.reject(new Error("n/a")),
    [categoria],
  );
  if (!ok) {
    return (
      <p className="text-sm text-muted">
        Previsão disponível apenas para roubo, furto e lesão corporal (os demais
        tipos são raros demais por célula para um modelo honesto).
      </p>
    );
  }
  return (
    <div className="space-y-4 text-sm">
      <p className="rounded-md border border-amber-500/60 bg-amber-500/10 p-2 text-xs">
        {previsao?.aviso ??
          "Previsão de ocorrências registradas, não de crime real; pode reforçar vieses de policiamento."}
      </p>
      {previsao && (
        <p className="text-muted">
          Mapa: registros esperados de{" "}
          <strong className="text-foreground">
            {new Date(
              previsao.inicio_previsao + "T00:00:00",
            ).toLocaleDateString("pt-BR")}
          </strong>{" "}
          a{" "}
          <strong className="text-foreground">
            {new Date(previsao.fim_previsao + "T00:00:00").toLocaleDateString(
              "pt-BR",
            )}
          </strong>
          , por célula de ~5 km² com histórico suficiente.
        </p>
      )}
      {b.data && (
        <>
          <section>
            <h3 className="mb-1 font-semibold">
              Backtest ({b.data.modelos[0]?.n_origens} origens, últimas 24
              semanas)
            </h3>
            <table className="w-full text-xs">
              <caption className="sr-only">
                Métricas de backtest por modelo
              </caption>
              <thead>
                <tr className="text-left text-muted">
                  <th scope="col" className="py-1">
                    Modelo
                  </th>
                  <th scope="col" className="text-right">
                    Desvio ↓
                  </th>
                  <th scope="col" className="text-right">
                    Captura top-10% ↑
                  </th>
                </tr>
              </thead>
              <tbody>
                {[...b.data.modelos].reverse().map((m) => (
                  <tr
                    key={m.modelo}
                    className={m.modelo === "glm_viz" ? "font-semibold" : ""}
                  >
                    <td className="py-0.5">
                      {NOMES_MODELO[m.modelo] ?? m.modelo}
                    </td>
                    <td className="text-right tabular-nums">
                      {m.desvio_poisson.toLocaleString("pt-BR")}
                    </td>
                    <td className="text-right tabular-nums">
                      {(m.captura_top10 * 100).toLocaleString("pt-BR", {
                        maximumFractionDigits: 1,
                      })}
                      %
                    </td>
                  </tr>
                ))}
                <tr className="text-muted">
                  <td className="py-0.5">Teto (oráculo)</td>
                  <td />
                  <td className="text-right tabular-nums">
                    {(b.data.captura_teto_oraculo * 100).toLocaleString(
                      "pt-BR",
                      { maximumFractionDigits: 1 },
                    )}
                    %
                  </td>
                </tr>
              </tbody>
            </table>
          </section>
          <p className="rounded-md border border-border p-2">
            {b.data.leitura}
          </p>
          <p className="text-xs text-muted">{b.data.metodo}</p>
        </>
      )}
      {b.error && (
        <p role="alert" className="text-red-600 dark:text-red-400">
          {b.error}
        </p>
      )}
    </div>
  );
}
