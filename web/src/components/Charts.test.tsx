import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  HourDowGrid,
  LineChart,
  MultiLineChart,
  SeasonBars,
  YearOverlay,
} from "@/components/Charts";

describe("Charts", () => {
  it("LineChart expõe rótulo acessível, unidade e rótulos mês/ano em séries curtas", () => {
    render(
      <LineChart
        label="Série de teste"
        data={[
          { mes: "2025-01-01", n: 10 },
          { mes: "2025-02-01", n: 20 },
          { mes: "2026-01-01", n: 15 },
        ]}
      />,
    );
    expect(
      screen.getByRole("img", { name: "Série de teste" }),
    ).toBeInTheDocument();
    expect(screen.getByText("jan/25")).toBeInTheDocument();
    expect(
      screen.getByText("ocorrências registradas por mês"),
    ).toBeInTheDocument();
  });

  it("LineChart marca só os anos em séries longas", () => {
    const data = Array.from({ length: 30 }, (_, i) => {
      const d = new Date(2024, i, 1);
      return {
        mes: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`,
        n: 10 + i,
      };
    });
    render(<LineChart label="Longa" data={data} />);
    expect(screen.getByText("2025")).toBeInTheDocument();
    expect(screen.getByText("2026")).toBeInTheDocument();
  });

  it("MultiLineChart tem legenda com uma entrada por série", () => {
    render(
      <MultiLineChart
        label="Duas séries"
        unit="taxa"
        series={[
          {
            name: "Campinas",
            points: [
              { x: "2025-01-01", y: 1 },
              { x: "2025-02-01", y: 2 },
            ],
          },
          {
            name: "Santos",
            points: [
              { x: "2025-01-01", y: 3 },
              { x: "2025-02-01", y: 1 },
            ],
          },
        ]}
      />,
    );
    expect(screen.getByText("Campinas")).toBeInTheDocument();
    expect(screen.getByText("Santos")).toBeInTheDocument();
  });

  it("YearOverlay gera uma série por ano", () => {
    render(
      <YearOverlay
        label="Anos"
        data={[
          { mes: "2024-01-01", n: 1 },
          { mes: "2024-02-01", n: 2 },
          { mes: "2025-01-01", n: 3 },
          { mes: "2025-02-01", n: 4 },
        ]}
      />,
    );
    expect(screen.getByText("2024")).toBeInTheDocument();
    expect(screen.getByText("2025")).toBeInTheDocument();
  });

  it("LineChart não renderiza com menos de 2 pontos", () => {
    const { container } = render(
      <LineChart label="x" data={[{ mes: "2025-01-01", n: 1 }]} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("SeasonBars desenha 12 meses", () => {
    render(
      <SeasonBars
        data={Array.from({ length: 12 }, (_, i) => ({ mes: i + 1, indice: 1 }))}
      />,
    );
    expect(screen.getByText("jan")).toBeInTheDocument();
    expect(screen.getByText("dez")).toBeInTheDocument();
  });

  it("HourDowGrid avisa quando não há dados", () => {
    render(<HourDowGrid data={[]} />);
    expect(screen.getByText(/Sem dados suficientes/)).toBeInTheDocument();
  });
});
