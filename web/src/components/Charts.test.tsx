import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { HourDowGrid, LineChart, SeasonBars } from "@/components/Charts";

describe("Charts", () => {
  it("LineChart expõe rótulo acessível e rótulos de ano", () => {
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
    expect(screen.getByText("2026")).toBeInTheDocument();
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
