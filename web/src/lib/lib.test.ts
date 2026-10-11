import { describe, expect, it } from "vitest";
import { rampColor } from "@/components/colorRamp";
import { scaleMax } from "@/components/scale";
import {
  isoDate,
  lastCompleteMonthEnd,
  monthsBack,
  yearOverYearWindows,
} from "@/lib/dates";

describe("dates", () => {
  it("monthsBack inclui o mês de fim e começa no dia 1", () => {
    expect(monthsBack("2026-09-06", 12)).toBe("2025-10-01");
    expect(monthsBack("2026-01-15", 3)).toBe("2025-11-01");
  });

  it("lastCompleteMonthEnd recua se a semana completa não fecha o mês", () => {
    expect(isoDate(lastCompleteMonthEnd("2026-08-23"))).toBe("2026-07-31");
    expect(isoDate(lastCompleteMonthEnd("2026-08-31"))).toBe("2026-08-31");
    expect(isoDate(lastCompleteMonthEnd("2026-01-10"))).toBe("2025-12-31");
  });
});

describe("janelas ano a ano", () => {
  it("usa 12 meses completos vs. 12 anteriores, sem deslocar por fuso", () => {
    expect(yearOverYearWindows("2026-08-23")).toEqual({
      iniA: "2024-08-01",
      fimA: "2025-07-31",
      iniB: "2025-08-01",
      fimB: "2026-07-31",
    });
  });
});

describe("escala de cor", () => {
  it("rampColor limita t a [0, 1] e interpola", () => {
    expect(rampColor(-1)).toEqual(rampColor(0));
    expect(rampColor(5)).toEqual(rampColor(1));
    const mid = rampColor(0.5);
    expect(mid[0]).toBeGreaterThan(rampColor(1)[0] - 1);
    expect(mid[1]).toBeLessThan(rampColor(0)[1]);
  });

  it("scaleMax usa o percentil 98 e nunca menos que 2", () => {
    expect(scaleMax([])).toBe(1);
    expect(scaleMax([{ h3: "a", n: 1 }])).toBe(2);
    const cells = Array.from({ length: 100 }, (_, i) => ({
      h3: String(i),
      n: i + 1,
    }));
    cells.push({ h3: "outlier", n: 100000 });
    expect(scaleMax(cells)).toBeLessThan(1000); // outlier não domina a escala
  });
});
