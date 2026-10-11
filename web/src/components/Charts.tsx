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

export function LineChart({
  data,
  label,
}: {
  data: { mes: string; n: number }[];
  label: string;
}) {
  if (data.length < 2) return null;
  const W = 340;
  const H = 120;
  const pad = { l: 38, r: 6, t: 8, b: 18 };
  const max = Math.max(...data.map((d) => d.n));
  const x = (i: number) =>
    pad.l + (i / (data.length - 1)) * (W - pad.l - pad.r);
  const y = (v: number) => pad.t + (1 - v / max) * (H - pad.t - pad.b);
  const path = data
    .map((d, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(d.n).toFixed(1)}`)
    .join(" ");
  const years = data
    .map((d, i) => ({ d, i }))
    .filter(({ d }) => d.mes.endsWith("-01-01"));
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="w-full"
      role="img"
      aria-label={label}
    >
      <line
        x1={pad.l}
        x2={W - pad.r}
        y1={y(0)}
        y2={y(0)}
        stroke="var(--border)"
      />
      <text
        x={pad.l - 4}
        y={pad.t + 4}
        textAnchor="end"
        fontSize="9"
        fill="var(--muted)"
      >
        {fmt(max)}
      </text>
      <text
        x={pad.l - 4}
        y={y(0)}
        textAnchor="end"
        fontSize="9"
        fill="var(--muted)"
      >
        0
      </text>
      <path d={path} fill="none" stroke="var(--accent)" strokeWidth="2" />
      {years.map(({ d, i }) => (
        <text
          key={d.mes}
          x={x(i)}
          y={H - 4}
          fontSize="9"
          textAnchor="middle"
          fill="var(--muted)"
        >
          {d.mes.slice(0, 4)}
        </text>
      ))}
    </svg>
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
