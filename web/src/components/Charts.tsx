import { rampColor } from "@/components/colorRamp";

const MESES = [
  "jan",
  "fev",
  "mar",
  "abr",
  "mai",
  "jun",
  "jul",
  "ago",
  "set",
  "out",
  "nov",
  "dez",
];
const DIAS = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];

const fmt = (n: number) => n.toLocaleString("pt-BR");

export type Serie = { name: string; points: { x: string; y: number }[] };

const SERIES_COLORS = [
  "var(--series-1)",
  "var(--series-2)",
  "var(--series-3)",
  "var(--series-4)",
];
// O traço também muda por série: a cor não é o único meio de distinguir.
const SERIES_DASH = ["", "6 3", "2 3", "9 3 2 3"];

function niceMax(v: number) {
  if (v <= 0) return 1;
  const p = 10 ** Math.floor(Math.log10(v));
  const f = v / p;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
}

/**
 * Linhas no tempo (eixo x mensal). Eixo y com unidade e gradeado; cada ponto mostra o valor
 * ao passar o mouse; legenda com amostra de cor e traço quando há mais de uma série.
 */
export function MultiLineChart({
  series,
  label,
  unit,
  height = 140,
  width = 360,
  xLabel = "year",
}: {
  series: Serie[];
  label: string;
  unit: string;
  height?: number;
  /** Largura lógica do SVG: use ~720 em áreas largas para manter o texto legível. */
  width?: number;
  xLabel?: "year" | "month";
}) {
  const xs = [
    ...new Set(series.flatMap((s) => s.points.map((p) => p.x))),
  ].sort();
  if (xs.length < 2) return null;
  const W = width;
  const H = height;
  const pad = { l: 44, r: 8, t: 16, b: 20 };
  const max = niceMax(
    Math.max(...series.flatMap((s) => s.points.map((p) => p.y))),
  );
  const xi = new Map(xs.map((v, i) => [v, i]));
  const x = (v: string) =>
    pad.l + ((xi.get(v) ?? 0) / (xs.length - 1)) * (W - pad.l - pad.r);
  const y = (v: number) => pad.t + (1 - v / max) * (H - pad.t - pad.b);
  const ticks = [0, max / 2, max];
  // Séries curtas (≤ 24 meses) marcam meses a cada trimestre; longas marcam só os anos.
  const xticks =
    xLabel === "month"
      ? xs.map((v) => ({ v, t: MESES[Number(v.slice(5, 7)) - 1] }))
      : xs.length <= 24
        ? xs
            .filter((_, i) => i % 3 === 0)
            .map((v) => ({
              v,
              t: `${MESES[Number(v.slice(5, 7)) - 1]}/${v.slice(2, 4)}`,
            }))
        : xs
            .filter((v) => v.slice(5, 7) === "01")
            .map((v) => ({ v, t: v.slice(0, 4) }));
  const fmtV = (v: number) =>
    v.toLocaleString("pt-BR", { maximumFractionDigits: 1 });
  const fmtX = (v: string) =>
    xLabel === "year"
      ? `${MESES[Number(v.slice(5, 7)) - 1]}/${v.slice(0, 4)}`
      : MESES[Number(v.slice(5, 7)) - 1];
  return (
    <figure>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-label={label}
      >
        <text x={pad.l} y={9} fontSize="9" fill="var(--muted)">
          {unit}
        </text>
        {ticks.map((tk) => (
          <g key={tk}>
            <line
              x1={pad.l}
              x2={W - pad.r}
              y1={y(tk)}
              y2={y(tk)}
              stroke="var(--border)"
              strokeDasharray={tk ? "2 3" : ""}
            />
            <text
              x={pad.l - 4}
              y={y(tk) + 3}
              textAnchor="end"
              fontSize="9"
              fill="var(--muted)"
            >
              {fmtV(tk)}
            </text>
          </g>
        ))}
        {series.map((s, si) => {
          const pts = s.points.filter((p) => xi.has(p.x));
          const d = pts
            .map(
              (p, i) =>
                `${i ? "L" : "M"}${x(p.x).toFixed(1)},${y(p.y).toFixed(1)}`,
            )
            .join(" ");
          const color = SERIES_COLORS[si % SERIES_COLORS.length];
          return (
            <g key={s.name}>
              <path
                d={d}
                fill="none"
                stroke={color}
                strokeWidth="2"
                strokeDasharray={SERIES_DASH[si % SERIES_DASH.length]}
              />
              {pts.map((p) => (
                <circle
                  key={p.x}
                  cx={x(p.x)}
                  cy={y(p.y)}
                  r={2.6}
                  fill={color}
                  opacity={0.001}
                  className="hover:opacity-100"
                >
                  <title>{`${s.name} · ${fmtX(p.x)}: ${fmtV(p.y)} ${unit}`}</title>
                </circle>
              ))}
            </g>
          );
        })}
        {xticks.map(({ v, t }) => (
          <text
            key={v}
            x={x(v)}
            y={H - 5}
            fontSize="9"
            textAnchor="middle"
            fill="var(--muted)"
          >
            {t}
          </text>
        ))}
      </svg>
      {series.length > 1 && (
        <figcaption className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
          {series.map((s, si) => (
            <span key={s.name} className="inline-flex items-center gap-1.5">
              <svg width="22" height="8" aria-hidden="true">
                <line
                  x1="0"
                  x2="22"
                  y1="4"
                  y2="4"
                  stroke={SERIES_COLORS[si % SERIES_COLORS.length]}
                  strokeWidth="2"
                  strokeDasharray={SERIES_DASH[si % SERIES_DASH.length]}
                />
              </svg>
              {s.name}
            </span>
          ))}
        </figcaption>
      )}
    </figure>
  );
}

export function LineChart({
  data,
  label,
  unit = "ocorrências registradas por mês",
}: {
  data: { mes: string; n: number }[];
  label: string;
  unit?: string;
}) {
  return (
    <MultiLineChart
      label={label}
      unit={unit}
      series={[
        { name: "Registros", points: data.map((d) => ({ x: d.mes, y: d.n })) },
      ]}
    />
  );
}

/** Comparação entre anos: uma linha por ano completo ou parcial, eixo jan–dez. */
export function YearOverlay({
  data,
  label,
}: {
  data: { mes: string; n: number }[];
  label: string;
}) {
  const byYear = new Map<string, { x: string; y: number }[]>();
  for (const d of data) {
    const y = d.mes.slice(0, 4);
    if (!byYear.has(y)) byYear.set(y, []);
    // Todos os anos no mesmo eixo: usamos um ano fixo para posicionar o mês.
    byYear.get(y)!.push({ x: `2000-${d.mes.slice(5, 7)}-01`, y: d.n });
  }
  const years = [...byYear.keys()].sort().slice(-4);
  return (
    <MultiLineChart
      label={label}
      unit="registros por mês"
      xLabel="month"
      series={years.map((y) => ({ name: y, points: byYear.get(y)! }))}
    />
  );
}

export function SeasonBars({
  data,
}: {
  data: { mes: number; indice: number }[];
}) {
  if (!data.length) return null;
  const W = 340;
  const H = 90;
  const max = Math.max(...data.map((d) => d.indice), 1.2);
  const bw = (W - 10) / 12;
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="w-full"
      role="img"
      aria-label="Índice sazonal por mês (1,0 = média)"
    >
      <line
        x1={0}
        x2={W}
        y1={(H - 16) * (1 - 1 / max)}
        y2={(H - 16) * (1 - 1 / max)}
        stroke="var(--muted)"
        strokeDasharray="3 3"
      />
      {data.map((d) => {
        const h = (d.indice / max) * (H - 16);
        return (
          <g key={d.mes}>
            <rect
              x={5 + (d.mes - 1) * bw + 2}
              y={H - 16 - h}
              width={bw - 4}
              height={h}
              fill="var(--accent)"
              opacity={0.85}
            >
              <title>{`${MESES[d.mes - 1]}: ${d.indice.toLocaleString("pt-BR")}`}</title>
            </rect>
            <text
              x={5 + (d.mes - 1) * bw + bw / 2}
              y={H - 4}
              fontSize="9"
              textAnchor="middle"
              fill="var(--muted)"
            >
              {MESES[d.mes - 1]}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export function HourDowGrid({
  data,
}: {
  data: { dow: number; hora: number; n: number }[];
}) {
  if (!data.length)
    return (
      <p className="text-xs text-muted">Sem dados suficientes de horário.</p>
    );
  const max = Math.max(...data.map((d) => d.n));
  const cell = new Map(data.map((d) => [`${d.dow}-${d.hora}`, d.n]));
  const W = 340;
  const lw = 26;
  const cw = (W - lw) / 24;
  const ch = 13;
  return (
    <svg
      viewBox={`0 0 ${W} ${7 * ch + 16}`}
      className="w-full"
      role="img"
      aria-label="Ocorrências por dia da semana e hora"
    >
      {DIAS.map((dia, r) => (
        <g key={dia}>
          <text
            x={lw - 4}
            y={r * ch + 10}
            fontSize="9"
            textAnchor="end"
            fill="var(--muted)"
          >
            {dia}
          </text>
          {Array.from({ length: 24 }, (_, h) => {
            const n = cell.get(`${r}-${h}`) ?? 0;
            return (
              <rect
                key={h}
                x={lw + h * cw}
                y={r * ch}
                width={cw - 1}
                height={ch - 1}
                rx={1.5}
                fill={
                  n ? `rgb(${rampColor(n / max).join(",")})` : "var(--border)"
                }
              >
                <title>{`${dia} ${h}h: ${fmt(n)}`}</title>
              </rect>
            );
          })}
        </g>
      ))}
      {[0, 6, 12, 18].map((h) => (
        <text
          key={h}
          x={lw + h * cw}
          y={7 * ch + 11}
          fontSize="9"
          fill="var(--muted)"
        >
          {h}h
        </text>
      ))}
    </svg>
  );
}
