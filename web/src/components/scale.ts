import type { Cell } from "@/lib/api";

/** Máximo da escala de cor: percentil 98 das contagens (evita que outliers apaguem o resto). */
export function scaleMax(cells: Cell[]): number {
  if (!cells.length) return 1;
  const sorted = cells.map((c) => c.n).sort((a, b) => a - b);
  return Math.max(sorted[Math.floor(sorted.length * 0.98)] ?? 1, 2);
}
