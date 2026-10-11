// Padrão decorativo de hexágonos (SVG determinístico, sem dados reais).
const R = 22;
const W = Math.sqrt(3) * R;

function hexPath(cx: number, cy: number, r: number) {
  const pts = Array.from({ length: 6 }, (_, i) => {
    const a = (Math.PI / 180) * (60 * i - 30);
    return `${(cx + r * Math.cos(a)).toFixed(1)},${(cy + r * Math.sin(a)).toFixed(1)}`;
  });
  return `M${pts.join("L")}Z`;
}

export function HexPattern({ className = "" }: { className?: string }) {
  const cells: { x: number; y: number; v: number }[] = [];
  for (let row = 0; row < 9; row++) {
    for (let col = 0; col < 12; col++) {
      const x = col * W + (row % 2 ? W / 2 : 0) + 20;
      const y = row * R * 1.5 + 24;
      // "calor" suave e determinístico, concentrado no centro-direita
      const d = Math.hypot(col - 7.5, row - 4);
      const v =
        Math.max(0, 1 - d / 6) *
        (0.55 + 0.45 * Math.sin(col * 1.7 + row * 2.3) ** 2);
      cells.push({ x, y, v });
    }
  }
  return (
    <svg
      viewBox="0 0 490 310"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      {cells.map((c, i) => (
        <path
          key={i}
          d={hexPath(c.x, c.y, R - 2)}
          fill="var(--accent)"
          fillOpacity={0.06 + c.v * 0.8}
          stroke="var(--accent)"
          strokeOpacity={0.25}
        />
      ))}
    </svg>
  );
}
