// ColorBrewer YlOrRd (sequencial, seguro para daltonismo)
const RAMP: [number, number, number][] = [
  [255, 237, 160],
  [254, 178, 76],
  [240, 59, 32],
  [128, 0, 38],
];

export function rampColor(t: number): [number, number, number] {
  const x = Math.min(Math.max(t, 0), 1) * (RAMP.length - 1);
  const i = Math.min(Math.floor(x), RAMP.length - 2);
  const f = x - i;
  return RAMP[i].map((c, k) => Math.round(c + (RAMP[i + 1][k] - c) * f)) as [
    number,
    number,
    number,
  ];
}
