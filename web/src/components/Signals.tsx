import Link from "next/link";
import { Badge, fmtDate } from "@/components/ui";
import type { Historico, HistoricoStatus } from "@/lib/api";

const STATUS: Record<HistoricoStatus, { rotulo: string; dica: string }> = {
  novo: {
    rotulo: "Novo",
    dica: "Não aparecia na avaliação anterior (4 semanas antes), quando a série já era avaliável.",
  },
  persistente: {
    rotulo: "Persistente",
    dica: "Também foi detectado na avaliação anterior.",
  },
  historico_insuficiente: {
    rotulo: "Histórico insuficiente",
    dica: "A série não era avaliável na avaliação anterior: não dá para dizer se é novo.",
  },
  deixou_de_ser_detectado: {
    rotulo: "Deixou de ser detectado",
    dica: "O critério deixou de ser atendido. Isso não significa que a situação foi resolvida.",
  },
  sem_avaliacao_atual: {
    rotulo: "Sem avaliação atual",
    dica: "A série não pôde ser avaliada agora.",
  },
  recorrente: {
    rotulo: "Recorrente",
    dica: "Picos em mais de uma avaliação no último ano.",
  },
  anterior: {
    rotulo: "Anterior",
    dica: "Detectado só em avaliações passadas.",
  },
};

/** Minigráfico da intensidade nas avaliações (a cada 4 semanas, último ano). */
function Sparkline({ h }: { h: Historico }) {
  const pts = h.serie.filter((p) => p.valor != null) as {
    origem: string;
    valor: number;
  }[];
  if (pts.length < 2) return null;
  const W = 90;
  const H = 22;
  const vs = pts.map((p) => p.valor);
  const min = Math.min(...vs, 1);
  const max = Math.max(...vs, 1);
  const t0 = new Date(pts[0].origem).getTime();
  const t1 = new Date(pts[pts.length - 1].origem).getTime();
  const x = (s: string) =>
    2 + ((new Date(s).getTime() - t0) / Math.max(t1 - t0, 1)) * (W - 4);
  const y = (v: number) =>
    H - 2 - ((v - min) / Math.max(max - min, 1e-9)) * (H - 4);
  return (
    <svg
      width={W}
      height={H}
      role="img"
      aria-label={`Intensidade em ${pts.length} avaliações, de ${fmtDate(pts[0].origem)} a ${fmtDate(pts[pts.length - 1].origem)}`}
    >
      <line
        x1={0}
        x2={W}
        y1={y(1)}
        y2={y(1)}
        stroke="var(--border)"
        strokeDasharray="2 2"
      />
      {pts.map((p) => (
        <circle
          key={p.origem}
          cx={x(p.origem)}
          cy={y(p.valor)}
          r={2}
          fill="var(--foreground)"
        >
          <title>{`${fmtDate(p.origem)}: ${p.valor.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}`}</title>
        </circle>
      ))}
    </svg>
  );
}

export function HistoryLine({ h }: { h: Historico }) {
  const s = STATUS[h.status];
  return (
    <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md bg-surface-2 px-2 py-1.5 text-xs">
      <span title={s.dica}>
        <Badge
          tone={
            h.status === "persistente" || h.status === "recorrente"
              ? "accent"
              : "neutral"
          }
        >
          {s.rotulo}
        </Badge>
      </span>
      <span className="text-muted">
        1ª detecção {fmtDate(h.primeira_deteccao)} · em {h.deteccoes} de{" "}
        {h.origens_avaliadas || h.deteccoes} avaliações
        {h.mudou_direcao && " · já foi detectado na direção oposta"}
      </span>
      <Sparkline h={h} />
      <span className="sr-only">{s.dica}</span>
    </div>
  );
}

/** Diferença entre os tipos de informação do produto, usada no Radar e no painel. */
export function SignalGlossary() {
  return (
    <dl className="space-y-2 text-sm">
      <div>
        <dt className="font-medium">Registro histórico</dt>
        <dd className="text-muted">
          O que foi registrado em BOs. Mapa, séries e rankings. Não é o crime
          real.
        </dd>
      </div>
      <div>
        <dt className="font-medium">Pico semanal</dt>
        <dd className="text-muted">
          Uma semana fora do comum. Costuma ser evento de massa ou lote de
          registros.
        </dd>
      </div>
      <div>
        <dt className="font-medium">Mudança persistente</dt>
        <dd className="text-muted">
          Novo patamar por semanas, descontado o movimento do estado. Cerca de 1
          em cada 3 sinais não se confirma nas semanas seguintes ({" "}
          <Link className="underline" href="/qualidade#mudancas">
            avaliação
          </Link>
          ).
        </dd>
      </div>
      <div>
        <dt className="font-medium">Previsão</dt>
        <dd className="text-muted">
          Estimativa experimental de registros futuros. Não é observação.
        </dd>
      </div>
    </dl>
  );
}
