import { cellToBoundary } from "h3-js";
import { rampColor } from "@/components/colorRamp";
import type { Cell } from "@/lib/api";

/** Mapa estático em SVG (para o relatório impresso): hexágonos H3 em projeção equirretangular. */
export function HexSvgMap({
  cells,
  max,
  label,
}: {
  cells: Cell[];
  max: number;
  label: string;
}) {
  if (!cells.length) return null;
  const polys = cells.map((c) => ({ c, b: cellToBoundary(c.h3) }));
  // Enquadra onde está a maior parte das ocorrências (quantis 5–95% ponderados), não o estado todo.
  const centers = polys.map(({ c, b }) => ({
    n: c.n,
    lat: b.reduce((s, p) => s + p[0], 0) / b.length,
    lng: b.reduce((s, p) => s + p[1], 0) / b.length,
  }));
  const wq = (key: "lat" | "lng", q: number) => {
    const sorted = [...centers].sort((a, b) => a[key] - b[key]);
    const total = sorted.reduce((s, c) => s + c.n, 0);
    let acc = 0;
    for (const c of sorted) {
      acc += c.n;
      if (acc >= q * total) return c[key];
    }
    return sorted[sorted.length - 1][key];
  };
  const padLat = (wq("lat", 0.95) - wq("lat", 0.05)) * 0.2 + 0.02;
  const padLng = (wq("lng", 0.95) - wq("lng", 0.05)) * 0.2 + 0.02;
  const minLat = wq("lat", 0.05) - padLat;
  const maxLat = wq("lat", 0.95) + padLat;
  const minLng = wq("lng", 0.05) - padLng;
  const maxLng = wq("lng", 0.95) + padLng;
  const k = Math.cos((((minLat + maxLat) / 2) * Math.PI) / 180);
  const W = 1000;
  const H = Math.round((W * (maxLat - minLat)) / ((maxLng - minLng) * k));
  const px = (lng: number) => ((lng - minLng) / (maxLng - minLng)) * W;
  const py = (lat: number) => ((maxLat - lat) / (maxLat - minLat)) * H;
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="w-full overflow-hidden rounded border border-border"
      role="img"
      aria-label={label}
    >
      <rect width={W} height={H} fill="var(--background)" />
      {polys.map(({ c, b }) => (
        <polygon
          key={c.h3}
          points={b
            .map(([lat, lng]) => `${px(lng).toFixed(1)},${py(lat).toFixed(1)}`)
            .join(" ")}
          fill={`rgb(${rampColor(Math.log1p(c.n) / Math.log1p(max)).join(",")})`}
        />
      ))}
    </svg>
  );
}
