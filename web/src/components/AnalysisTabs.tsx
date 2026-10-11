"use client";

import {
  HourDowGrid,
  LineChart,
  SeasonBars,
  YearOverlay,
} from "@/components/Charts";
import {
  Delta,
  fmtDate,
  fmtInt,
  fmtMonth,
  fmtNum,
  Notice,
  StateMessage,
  TextLink,
} from "@/components/ui";
import { analysis, forecast, type Previsao } from "@/lib/api";
import { yearOverYearWindows } from "@/lib/dates";
import { useLoad } from "@/lib/useLoad";

type Props = {
  categoria: string;
  cdIbge: number | null;
  municipio: string | null;
  completoAte: string;
};

export function TimeTab({ categoria, cdIbge, municipio }: Props) {
  const t = useLoad(
    () => analysis.tendencia({ categoria, cd_ibge: cdIbge ?? undefined }),
    [categoria, cdIbge],
  );
  const h = useLoad(
    () => analysis.horaDia({ categoria, cd_ibge: cdIbge ?? undefined }),
    [categoria, cdIbge],
  );
  const where = municipio ?? "Estado de São Paulo";
  return (
    <div className="space-y-5">
      <p className="text-xs text-muted">
        Recorte: <strong className="text-foreground">{where}</strong>. Escolha
        um município no filtro do mapa ou clique no ranking.
      </p>
      <StateMessage
        loading={t.loading}
        error={t.error}
        onRetry={t.retry}
        empty={t.data?.suprimido}
        emptyText="Poucas ocorrências neste recorte: série oculta para proteger a privacidade."
      >
        {t.data && (
          <>
            <section>
              <h3 className="mb-1 text-sm font-semibold">
                Registros por mês (meses completos)
              </h3>
              <LineChart
                data={t.data.serie}
                label={`Série mensal de registros — ${where}`}
              />
              <dl className="mt-2 grid grid-cols-2 gap-3 text-sm">
                <div>
                  <dt className="text-xs text-muted">
                    Últimos 12 meses vs. 12 anteriores
                  </dt>
                  <dd className="text-lg font-semibold">
                    <Delta value={t.data.variacao_12m_pct} />
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">
                    Inclinação (últimos 24 meses)
                  </dt>
                  <dd className="text-lg font-semibold">
                    <Delta value={t.data.inclinacao_pct_ano} suffix="%/ano" />
                  </dd>
                </div>
              </dl>
            </section>
            <section>
              <h3 className="mb-1 text-sm font-semibold">
                Comparação entre anos
              </h3>
              <YearOverlay
                data={t.data.serie}
                label={`Registros por mês, um traço por ano — ${where}`}
              />
              <p className="mt-1 text-xs text-muted">
                O ano mais recente termina no último mês completo.
              </p>
            </section>
            <section>
              <h3 className="mb-1 text-sm font-semibold">
                Sazonalidade (índice mensal)
              </h3>
              <SeasonBars data={t.data.sazonalidade} />
              <p className="mt-1 text-xs text-muted">
                1,0 = média do ano; calculado só com anos completos.
              </p>
            </section>
          </>
        )}
      </StateMessage>
      <section>
        <h3 className="mb-1 text-sm font-semibold">Dia da semana × hora</h3>
        <StateMessage
          loading={h.loading}
          error={h.error}
          onRetry={h.retry}
          empty={h.data?.length === 0}
        >
          {h.data && <HourDowGrid data={h.data} />}
        </StateMessage>
        <p className="mt-1 text-xs text-muted">
          Muitos BOs não informam a hora (furto: ~43%); o padrão vale só para os
          que informam.
        </p>
      </section>
      {t.data && (
        <p className="text-xs text-muted">
          {t.data.nota} Dados completos até {fmtDate(t.data.completo_ate)}.
        </p>
      )}
    </div>
  );
}

export function CompareBox({ categoria, cdIbge, completoAte }: Props) {
  const { iniA, fimA, iniB, fimB } = yearOverYearWindows(completoAte);
  const c = useLoad(
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
    <p className="mt-3 rounded-lg border border-border bg-background p-3 text-sm">
      {c.data.suprimido ? (
        "Comparação anual oculta (poucas ocorrências)."
      ) : (
        <>
          12 meses até {fmtMonth(fimB)} vs. 12 anteriores:{" "}
          <strong>
            <Delta value={c.data.variacao_pct} />
          </strong>{" "}
          <span className="text-muted">
            ({fmtInt(c.data.b)} vs. {fmtInt(c.data.a)})
          </span>
        </>
      )}
    </p>
  );
}

export function AlertsTab({ categoria, cdIbge, municipio }: Props) {
  const a = useLoad(
    () =>
      analysis.anomalias({
        categoria,
        cd_ibge: cdIbge ?? undefined,
        limit: 15,
      }),
    [categoria, cdIbge],
  );
  return (
    <div>
      <h3 className="text-sm font-semibold">
        Picos semanais recentes
        {municipio ? ` em ${municipio}` : " (por município)"}
      </h3>
      <div className="mt-2">
        <StateMessage
          loading={a.loading}
          error={a.error}
          onRetry={a.retry}
          empty={a.data?.itens.length === 0}
          emptyText="Nenhum pico semanal nas últimas 8 semanas completas para este recorte."
        >
          <ul className="space-y-2 text-sm">
            {a.data?.itens.map((i) => (
              <li
                key={`${i.id}-${i.semana}`}
                className="rounded-lg border border-border bg-background p-2.5"
              >
                <div className="flex justify-between gap-2">
                  <strong>{i.nome ?? i.id}</strong>
                  <span className="text-xs text-muted">
                    semana de {fmtDate(i.semana)}
                  </span>
                </div>
                <div className="tabular-nums text-muted">
                  {fmtInt(i.n)} registros vs. ~{fmtNum(i.esperado)} esperados (
                  {fmtNum(i.razao)}×)
                </div>
              </li>
            ))}
          </ul>
        </StateMessage>
      </div>
      {a.data && <p className="mt-3 text-xs text-muted">{a.data.metodo}</p>}
      <p className="mt-3 text-sm">
        <TextLink
          href={`/radar?categoria=${categoria}${cdIbge ? `&municipio=${cdIbge}` : ""}`}
        >
          Ver no Radar, com mudanças persistentes e variações →
        </TextLink>
      </p>
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
  const b = useLoad(() => forecast.backtest(categoria), [categoria], ok);
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
      <Notice tone="warning" title="Previsão experimental">
        {previsao?.aviso ??
          "Previsão de ocorrências registradas, não de crime real; pode reforçar vieses de policiamento."}
      </Notice>
      {previsao && (
        <p className="text-muted">
          Mapa: registros esperados de{" "}
          <strong className="text-foreground">
            {fmtDate(previsao.inicio_previsao)}
          </strong>{" "}
          a{" "}
          <strong className="text-foreground">
            {fmtDate(previsao.fim_previsao)}
          </strong>
          , por célula de ~5 km² com histórico suficiente.
        </p>
      )}
      <StateMessage loading={b.loading} error={b.error} onRetry={b.retry}>
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
                      Desvio (menor é melhor)
                    </th>
                    <th scope="col" className="text-right">
                      Captura top-10%
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
                        {fmtNum(m.desvio_poisson, 3)}
                      </td>
                      <td className="text-right tabular-nums">
                        {fmtNum(m.captura_top10 * 100)}%
                      </td>
                    </tr>
                  ))}
                  <tr className="text-muted">
                    <td className="py-0.5">Teto (oráculo)</td>
                    <td />
                    <td className="text-right tabular-nums">
                      {fmtNum(b.data.captura_teto_oraculo * 100)}%
                    </td>
                  </tr>
                </tbody>
              </table>
            </section>
            <p className="rounded-lg border border-border bg-background p-3">
              {b.data.leitura}
            </p>
            <p className="text-xs text-muted">{b.data.metodo}</p>
          </>
        )}
      </StateMessage>
    </div>
  );
}
