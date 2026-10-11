/** Primeiro dia do mês, `n` meses atrás (inclusive o mês de `fim`), em ISO (YYYY-MM-DD). */
export function monthsBack(fim: string, n: number): string {
  const d = new Date(fim + "T00:00:00");
  d.setMonth(d.getMonth() - n + 1, 1);
  const p = (x: number) => String(x).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

/** Último dia do último mês totalmente completo, dado o fim da semana completa mais recente. */
export function lastCompleteMonthEnd(completoAte: string): Date {
  const ref = new Date(completoAte + "T00:00:00");
  const lastDay = new Date(ref.getFullYear(), ref.getMonth() + 1, 0).getDate();
  return new Date(
    ref.getFullYear(),
    ref.getMonth() + (ref.getDate() >= lastDay ? 1 : 0),
    0,
  );
}

export function isoDate(d: Date): string {
  const p = (x: number) => String(x).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}
