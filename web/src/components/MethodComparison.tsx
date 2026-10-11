import { Card, fmtInt, fmtNum, Notice } from "@/components/ui";
import type { Mudancas } from "@/lib/api";

const NOME: Record<string, string> = {
  referencia: "Referência simples",
  share: "Participação (CUSUM)",
  "share+bh": "Participação + BH (adotado)",
  sazonal: "Participação + sazonalidade municipal",
  "sazonal+bh": "Sazonal + BH",
};
const ORDEM = ["referencia", "share", "share+bh", "sazonal", "sazonal+bh"];

function Lift({ v }: { v: number | null }) {
  return (
    <span className="tabular-nums">{v == null ? "—" : `${fmtNum(v, 2)}×`}</span>
  );
}

/** Avaliação comparativa do detector: mesmo conjunto de séries para todos os métodos. */
export function MethodComparison({ m }: { m: Mudancas }) {
  if (!m.comparacao.length) return null;
  const geral = m.comparacao
    .filter((c) => c.recorte_tipo === "geral" && (c.h === 5 || c.h == null))
    .sort((a, b) => ORDEM.indexOf(a.metodo) - ORDEM.indexOf(b.metodo));
  const faixas = ["3-10/sem", "10-30/sem", ">=30/sem"];
  const porFaixa = (metodo: string, f: string) =>
    m.comparacao.find(
      (c) =>
        c.recorte_tipo === "faixa" &&
        c.recorte === f &&
        c.metodo === metodo &&
        (c.h === 5 || c.h == null),
    );
  const sens = m.comparacao
    .filter(
      (c) =>
        c.recorte_tipo === "sensibilidade_h" &&
        (c.metodo === "share" || c.metodo === "share+bh"),
    )
    .sort(
      (a, b) =>
        a.metodo.localeCompare(b.metodo) || a.recorte.localeCompare(b.recorte),
    );
  const pct = (v?: number) => `${fmtNum((v ?? 0) * 100)}%`;
  const fp = (saz: boolean, nivel: number, metodo: string) =>
    m.simulacao_metodos.find(
      (s) =>
        s.sazonalidade_municipal === saz &&
        s.nivel_semanal === nivel &&
        s.cenario === "sem_mudanca" &&
        s.metodo === metodo,
    )?.taxa_sinal;

  return (
    <Card
      title="Comparação de métodos (avaliação v3)"
      description="Todos os métodos avaliados no mesmo conjunto de séries e origens (2023–2026), com as mesmas métricas."
    >
      <div className="space-y-5 text-sm">
        <Notice tone="info" title="Decisão">
          Em produção: <strong>{m.metodo_versao ?? "—"}</strong>. O modelo com
          sazonalidade municipal foi avaliado e <strong>não adotado</strong>:
          sinaliza mais e confirma menos sob a verdade neutra (T1) em todas as
          faixas e anos; com encolhimento forte, converge para o modelo atual. O
          controle de falsas descobertas (BH) trouxe ganho pequeno e
          consistente.
        </Notice>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[40rem]">
            <caption className="mb-1 text-left font-medium">
              Confirmação fora da amostra (8 semanas seguintes) e ganho sobre o
              acaso
            </caption>
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted">
                <th scope="col" className="py-1.5">
                  Método
                </th>
                <th scope="col" className="text-right">
                  Sinais
                </th>
                <th scope="col" className="text-right">
                  Taxa
                </th>
                <th scope="col" className="text-right">
                  Confirma T1
                </th>
                <th scope="col" className="text-right">
                  Ganho T1
                </th>
                <th scope="col" className="text-right">
                  Confirma T2
                </th>
                <th scope="col" className="text-right">
                  Ganho T2
                </th>
              </tr>
            </thead>
            <tbody>
              {geral.map((c) => (
                <tr
                  key={c.metodo}
                  className={`border-b border-border/60 ${c.metodo === "share+bh" ? "font-semibold" : ""}`}
                >
                  <th scope="row" className="py-1.5 text-left font-normal">
                    {NOME[c.metodo] ?? c.metodo}
                  </th>
                  <td className="text-right tabular-nums">
                    {fmtInt(c.sinais)}
                  </td>
                  <td className="text-right tabular-nums">
                    {fmtNum((c.taxa_sinal ?? 0) * 100)}%
                  </td>
                  <td className="text-right tabular-nums">
                    {fmtNum(c.conf_t1)}%
                  </td>
                  <td className="text-right">
                    <Lift v={c.lift_t1} />
                  </td>
                  <td className="text-right tabular-nums">
                    {fmtNum(c.conf_t2)}%
                  </td>
                  <td className="text-right">
                    <Lift v={c.lift_t2} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-1 text-xs text-muted">
            T1: o patamar seguiu acima/abaixo do esperado pelo padrão estadual.
            T2: idem, descontando também a sazonalidade do município no ano
            anterior (favorece o modelo sazonal por construção). Ganho =
            confirmação ÷ confirmação por acaso.
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[30rem]">
            <caption className="mb-1 text-left font-medium">
              Ganho T1 por volume da série
            </caption>
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted">
                <th scope="col" className="py-1.5">
                  Método
                </th>
                {faixas.map((f) => (
                  <th key={f} scope="col" className="text-right">
                    {f.replace(">=", "≥ ")}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ORDEM.filter((o) => o !== "sazonal+bh").map((o) => (
                <tr key={o} className="border-b border-border/60">
                  <th scope="row" className="py-1.5 text-left font-normal">
                    {NOME[o]}
                  </th>
                  {faixas.map((f) => (
                    <td key={f} className="text-right">
                      <Lift v={porFaixa(o, f)?.lift_t1 ?? null} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {m.simulacao_metodos.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[30rem]">
              <caption className="mb-1 text-left font-medium">
                Falso alarme na simulação (sem mudança real), com e sem
                sazonalidade municipal
              </caption>
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted">
                  <th scope="col" className="py-1.5">
                    Método
                  </th>
                  <th scope="col" className="text-right">
                    10/sem, sem saz.
                  </th>
                  <th scope="col" className="text-right">
                    10/sem, com saz.
                  </th>
                  <th scope="col" className="text-right">
                    30/sem, sem saz.
                  </th>
                  <th scope="col" className="text-right">
                    30/sem, com saz.
                  </th>
                </tr>
              </thead>
              <tbody>
                {["referencia", "share", "sazonal"].map((o) => (
                  <tr key={o} className="border-b border-border/60">
                    <th scope="row" className="py-1.5 text-left font-normal">
                      {NOME[o]}
                    </th>
                    {[
                      [false, 10],
                      [true, 10],
                      [false, 30],
                      [true, 30],
                    ].map(([s, n]) => (
                      <td key={`${s}${n}`} className="text-right tabular-nums">
                        {fmtNum((fp(s as boolean, n as number, o) ?? 0) * 100)}%
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-1 text-xs text-muted">
              A sazonalidade municipal ajuda quando existe (30/sem:{" "}
              {pct(fp(true, 30, "share"))} → {pct(fp(true, 30, "sazonal"))}),
              mas o fator estimado com um ano de histórico adiciona ruído quando
              ela não existe (30/sem: {pct(fp(false, 30, "share"))} →{" "}
              {pct(fp(false, 30, "sazonal"))}).
            </p>
          </div>
        )}

        {m.fdr.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[26rem]">
              <caption className="mb-1 text-left font-medium">
                Lotes simulados com 10% de mudanças reais e sazonalidade
                municipal: falsas descobertas e poder
              </caption>
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted">
                  <th scope="col" className="py-1.5">
                    Método
                  </th>
                  <th scope="col" className="text-right">
                    Registros/sem.
                  </th>
                  <th scope="col" className="text-right">
                    Falsas descobertas
                  </th>
                  <th scope="col" className="text-right">
                    Poder
                  </th>
                </tr>
              </thead>
              <tbody>
                {m.fdr.map((f) => (
                  <tr
                    key={`${f.metodo}-${f.nivel_semanal}`}
                    className="border-b border-border/60"
                  >
                    <th scope="row" className="py-1.5 text-left font-normal">
                      {NOME[f.metodo] ?? f.metodo}
                    </th>
                    <td className="text-right tabular-nums">
                      {fmtNum(f.nivel_semanal, 0)}
                    </td>
                    <td className="text-right tabular-nums">
                      {fmtNum(f.fdp_media_pct)}%
                    </td>
                    <td className="text-right tabular-nums">
                      {fmtNum(f.poder_pct)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-1 text-xs text-muted">
              O BH quase não altera a proporção de falsas descobertas: os falsos
              alarmes vêm da sazonalidade não modelada, que também produz
              p-valores pequenos. O BH só controla a taxa de falsas descobertas
              quando o modelo nulo está correto.
            </p>
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          {sens.length > 0 && (
            <div>
              <p className="mb-1 font-medium">Sensibilidade ao limiar H</p>
              <ul className="space-y-0.5 text-xs">
                {sens.map((c) => (
                  <li
                    key={`${c.metodo}${c.recorte}`}
                    className="flex justify-between gap-2"
                  >
                    <span>
                      {NOME[c.metodo]} · {c.recorte}
                    </span>
                    <span className="tabular-nums">
                      {fmtInt(c.sinais)} sinais · <Lift v={c.lift_t1} />
                    </span>
                  </li>
                ))}
              </ul>
              <p className="mt-1 text-xs text-muted">
                H maior = menos sinais e ganho um pouco maior. Mantivemos H = 5
                (definido antes da avaliação) para não ajustar o método aos
                mesmos dados usados para avaliá-lo.
              </p>
            </div>
          )}
          {m.estabilidade.length > 0 && (
            <div>
              <p className="mb-1 font-medium">Estabilidade no tempo</p>
              <ul className="space-y-0.5 text-xs">
                {m.estabilidade.map((e) => (
                  <li key={e.metodo} className="flex justify-between gap-2">
                    <span>{NOME[e.metodo] ?? e.metodo}</span>
                    <span className="tabular-nums">
                      {fmtNum(e.reaparecem_pct)}% reaparecem 4 semanas depois
                    </span>
                  </li>
                ))}
              </ul>
              <p className="mt-1 text-xs text-muted">
                Menos da metade dos sinais reaparece na avaliação seguinte:
                acompanhe o histórico antes de concluir.
              </p>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}
