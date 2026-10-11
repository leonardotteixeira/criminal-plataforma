"use client";

import { MapboxOverlay } from "@deck.gl/mapbox";
import { H3HexagonLayer } from "@deck.gl/geo-layers";
import * as maplibregl from "maplibre-gl";
import { useEffect, useMemo, useRef } from "react";
import type { Cell } from "@/lib/api";
import { rampColor } from "@/components/colorRamp";
import { scaleMax } from "@/components/scale";
import { useDark } from "@/lib/useDark";

// O worker padrão não carrega sob o bundler; servimos o ESM copiado para /public.
maplibregl.setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");

const STYLE_LIGHT =
  "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";
const STYLE_DARK =
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

export type MapCell = Cell & { faixa?: string };

const FAIXA_T: Record<string, number> = { alta: 0.95, media: 0.5, baixa: 0.12 };

export function HeatMap({
  cells,
  mode = "contagem",
}: {
  cells: MapCell[];
  mode?: "contagem" | "previsao";
}) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);
  const dark = useDark();
  const max = useMemo(() => scaleMax(cells), [cells]);
  const forecast = mode === "previsao";

  useEffect(() => {
    if (!container.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: STYLE_LIGHT,
      center: [-46.64, -23.55],
      zoom: window.innerWidth < 640 ? 8.2 : 9.2,
      attributionControl: { compact: true },
    });
    map.addControl(
      new maplibregl.NavigationControl({ showCompass: false }),
      "top-right",
    );
    const overlay = new MapboxOverlay({ interleaved: false, layers: [] });
    map.addControl(overlay as unknown as maplibregl.IControl);
    mapRef.current = map;
    overlayRef.current = overlay;
    return () => {
      map.remove();
      mapRef.current = null;
      overlayRef.current = null;
    };
  }, []);

  useEffect(() => {
    mapRef.current?.setStyle(dark ? STYLE_DARK : STYLE_LIGHT);
  }, [dark]);

  useEffect(() => {
    overlayRef.current?.setProps({
      layers: [
        new H3HexagonLayer<MapCell>({
          id: "h3",
          data: cells,
          getHexagon: (d) => d.h3,
          getFillColor: (d) => [
            ...rampColor(
              forecast
                ? (FAIXA_T[d.faixa ?? "baixa"] ?? 0.1)
                : Math.log1p(d.n) / Math.log1p(max),
            ),
            forecast ? 170 : 190,
          ],
          extruded: false,
          stroked: false,
          pickable: true,
          highPrecision: false,
          updateTriggers: { getFillColor: [max, forecast] },
        }),
      ],
      getTooltip: ({ object }: { object?: MapCell }) =>
        object
          ? {
              text: forecast
                ? `~${object.n.toLocaleString("pt-BR")} registros esperados em 4 semanas
faixa de risco: ${object.faixa} (célula ~5 km²)`
                : `${object.n.toLocaleString("pt-BR")} ocorrências
(hexágono de ~0,7 km²)`,
            }
          : null,
    });
  }, [cells, max, forecast]);

  return (
    <div className="relative h-full w-full">
      <div
        ref={container}
        className="h-full w-full"
        role="img"
        aria-label="Mapa de calor de ocorrências por hexágono"
      />
      {forecast ? <ForecastLegend /> : <Legend max={max} />}
    </div>
  );
}

function Legend({ max }: { max: number }) {
  const stops = [0, 0.33, 0.66, 1]
    .map((t) => `rgb(${rampColor(t).join(",")})`)
    .join(", ");
  return (
    <div className="pointer-events-none absolute bottom-6 left-3 rounded-md border border-border bg-surface/90 p-2 text-xs shadow">
      <div className="mb-1 text-muted">Ocorrências por hexágono</div>
      <div
        className="h-2.5 w-40 rounded"
        style={{ background: `linear-gradient(to right, ${stops})` }}
      />
      <div className="mt-0.5 flex justify-between text-muted">
        <span>poucas</span>
        <span>≥ {max.toLocaleString("pt-BR")}</span>
      </div>
    </div>
  );
}

function ForecastLegend() {
  const items = [
    ["alta", "Alta (top 10%)"],
    ["media", "Média (10–30%)"],
    ["baixa", "Baixa"],
  ] as const;
  return (
    <div className="pointer-events-none absolute bottom-6 left-3 rounded-md border border-border bg-surface/90 p-2 text-xs shadow">
      <div className="mb-1 text-muted">Faixa de risco previsto (4 semanas)</div>
      {items.map(([k, label]) => (
        <div key={k} className="flex items-center gap-2">
          <span
            className="inline-block h-3 w-3 rounded-sm"
            style={{ background: `rgb(${rampColor(FAIXA_T[k]).join(",")})` }}
          />
          {label}
        </div>
      ))}
    </div>
  );
}
