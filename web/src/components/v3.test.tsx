import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { HourDowGrid, LineChart } from "@/components/Charts";
import { HistoryLine, SignalGlossary } from "@/components/Signals";
import type { Decomposicao, Historico, Robustez } from "@/lib/api";

const ROB: Robustez = {
  regiao: "Campinas",
  categoria: "drogas",
  veredito: "parcialmente_consistente",
  resumo: "Nenhuma janela aponta a direção oposta; novo patamar.",
  verificacoes: [
    {
      nome: "janela_6m",
      descricao: "Últimos 6 meses",
      variacao_pct: 2.1,
      direcao: "estavel",
      detalhe: "100 vs. 98",
    },
    {
      nome: "janela_12m",
      descricao: "Últimos 12 meses",
      variacao_pct: -75,
      direcao: "queda",
      detalhe: "1200 vs. 4800",
    },
  ],
  cobertura: ["79% dos registros têm local utilizável"],
};
const DEC: Decomposicao = {
  por: "categoria",
  regiao: "Campinas",
  categoria: null,
  inicio_anterior: "2024-06-01",
  fim_anterior: "2025-05-31",
  inicio: "2025-06-01",
  fim: "2026-05-31",
  total_anterior: 5000,
  total_atual: 4000,
  variacao_total_pct: -20,
  itens: [
    {
      chave: "drogas",
      nome: "Drogas",
      anterior: 4800,
      atual: 1200,
      variacao_abs: -3600,
      variacao_pct: -75,
      contribuicao_pct: 360,
    },
    {
      chave: "furto",
      nome: "Furto",
      anterior: 200,
      atual: 2800,
      variacao_abs: 2600,
      variacao_pct: 1300,
      contribuicao_pct: -260,
    },
  ],
  nao_publicados: 2,
  nota: "Decomposição aritmética.",
};

vi.mock("@/lib/api", async (orig) => {
  const mod = await orig<typeof import("@/lib/api")>();
  return {
    ...mod,
    analysis: {
      ...mod.analysis,
      robustez: vi.fn().mockResolvedValue(ROB),
      decomposicao: vi.fn().mockResolvedValue(DEC),
    },
  };
});

describe("gráficos com valores suprimidos", () => {
  it("LineChart interrompe a linha no ponto suprimido e explica", () => {
    const { container } = render(
      <LineChart
        label="Série"
        data={[
          { mes: "2025-01-01", n: 10 },
          { mes: "2025-02-01", n: null },
          { mes: "2025-03-01", n: 12 },
          { mes: "2025-04-01", n: 14 },
        ]}
      />,
    );
    const d = container.querySelector("path")!.getAttribute("d")!;
    expect(d.match(/M/g)).toHaveLength(2); // dois trechos, sem ligar o ponto oculto a zero
    expect(
      screen.getByText(/menos de 5 registros, ocultados/),
    ).toBeInTheDocument();
  });

  it("HourDowGrid hachura células suprimidas e diferencia de zero", () => {
    const data = Array.from({ length: 168 }, (_, i) => ({
      dow: Math.floor(i / 24),
      hora: i % 24,
      n: i === 0 ? null : i === 1 ? 0 : 10,
    }));
    const { container } = render(<HourDowGrid data={data} />);
    expect(
      container.querySelectorAll('rect[fill="url(#hachura-oculta)"]'),
    ).toHaveLength(1);
    expect(screen.getByText(/Células hachuradas \(1\)/)).toBeInTheDocument();
  });
});

describe("aba Investigar", () => {
  it("mostra o veredito, as verificações e a decomposição com aviso de não causalidade", async () => {
    const { InvestigateTab } = await import("@/components/InvestigateTab");
    render(
      <InvestigateTab
        categoria="drogas"
        nomeCategoria="Drogas"
        cdIbge={3509502}
        municipio="Campinas"
      />,
    );
    await waitFor(() =>
      expect(screen.getByText("Parcialmente consistente")).toBeInTheDocument(),
    );
    expect(screen.getByText("Últimos 12 meses")).toBeInTheDocument();
    expect(
      screen.getByText(/O que mudou no total de Campinas/),
    ).toBeInTheDocument();
    expect(screen.getByText(/2 item\(ns\) com menos de 5/)).toBeInTheDocument();
    expect(screen.getByText("Contribuição não é causa")).toBeInTheDocument();
  });
});

describe("histórico do radar", () => {
  const h: Historico = {
    status: "deixou_de_ser_detectado",
    primeira_deteccao: "2026-04-20",
    ultima_deteccao: "2026-07-20",
    deteccoes: 3,
    origens_avaliadas: 14,
    mudou_direcao: true,
    serie: [
      { origem: "2026-04-20", valor: 1.3 },
      { origem: "2026-05-18", valor: 1.4 },
    ],
    reconstruido: true,
  };

  it("mostra o estado, a contagem de avaliações e explica que encerramento não é resolução", () => {
    render(<HistoryLine h={h} />);
    expect(screen.getByText("Deixou de ser detectado")).toBeInTheDocument();
    expect(screen.getByText(/em 3 de 14 avaliações/)).toBeInTheDocument();
    expect(screen.getByText(/direção oposta/)).toBeInTheDocument();
    expect(
      screen.getByText(/não significa que a situação foi resolvida/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: /Intensidade em 2 avaliações/ }),
    ).toBeInTheDocument();
  });

  it("glossário distingue registro, pico, mudança e previsão", () => {
    render(<SignalGlossary />);
    for (const t of [
      "Registro histórico",
      "Pico semanal",
      "Mudança persistente",
      "Previsão",
    ]) {
      expect(screen.getByText(t)).toBeInTheDocument();
    }
  });
});
