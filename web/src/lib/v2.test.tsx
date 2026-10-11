import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Delta, StateMessage } from "@/components/ui";
import { ApiError, analysis, buildUrl } from "@/lib/api";
import { toCsv } from "@/lib/csv";
import { dadosAtualizados, loadSaved, removeView, saveView } from "@/lib/saved";

const LISTA = [
  { cd_ibge: 3550308, municipio: "São Paulo", populacao_2022: 11451999 },
  { cd_ibge: 3548500, municipio: "Santos", populacao_2022: 418608 },
  { cd_ibge: 3547809, municipio: "Santo André", populacao_2022: 748919 },
  { cd_ibge: 3509502, municipio: "Campinas", populacao_2022: 1139047 },
];

vi.mock("@/lib/api", async (orig) => {
  const mod = await orig<typeof import("@/lib/api")>();
  return { ...mod, municipiosLista: () => Promise.resolve(LISTA) };
});

describe("busca de municípios", () => {
  it("ignora acentos, prioriza quem começa com o termo e respeita exclusões", async () => {
    const { filtrarMunicipios } = await import("@/components/MunicipioPicker");
    expect(filtrarMunicipios(LISTA, "sao").map((m) => m.municipio)).toEqual([
      "São Paulo",
    ]);
    expect(filtrarMunicipios(LISTA, "santo").map((m) => m.municipio)).toEqual([
      "Santos",
      "Santo André",
    ]);
    expect(filtrarMunicipios(LISTA, "   ")).toEqual([]);
  });

  it("combobox: digita, navega com as setas e escolhe com Enter", async () => {
    const { MunicipioPicker } = await import("@/components/MunicipioPicker");
    const onChange = vi.fn();
    render(
      <MunicipioPicker
        label="Município"
        value={null}
        onChange={onChange}
        exclude={[3548500]}
      />,
    );
    const input = screen.getByRole("combobox", { name: "Município" });
    await waitFor(() => expect(input).not.toBeDisabled());
    fireEvent.change(input, { target: { value: "sant" } });
    expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual([
      expect.stringContaining("Santo André"),
    ]);
    fireEvent.change(input, { target: { value: "a" } });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange.mock.calls[0][0].cd_ibge).toBeTypeOf("number");
  });

  it("mostra estado vazio quando nada corresponde", async () => {
    const { MunicipioPicker } = await import("@/components/MunicipioPicker");
    render(
      <MunicipioPicker label="Município" value={null} onChange={() => {}} />,
    );
    const input = screen.getByRole("combobox");
    await waitFor(() => expect(input).not.toBeDisabled());
    fireEvent.change(input, { target: { value: "xyz" } });
    expect(
      screen.getByText("Nenhum município encontrado."),
    ).toBeInTheDocument();
  });
});

describe("análises salvas", () => {
  beforeEach(() => localStorage.clear());

  it("salva, substitui a mesma URL e remove", () => {
    expect(
      saveView({
        titulo: "A",
        url: "/dashboard?categoria=roubo",
        dados_ate: "2026-08-30",
      }),
    ).toBe(true);
    saveView({
      titulo: "A2",
      url: "/dashboard?categoria=roubo",
      dados_ate: "2026-08-30",
    });
    saveView({ titulo: "B", url: "/comparar?m=1", dados_ate: "2026-08-30" });
    const items = loadSaved();
    expect(items.map((i) => i.titulo)).toEqual(["B", "A2"]);
    removeView(items[0].id);
    expect(loadSaved().map((i) => i.titulo)).toEqual(["A2"]);
  });

  it("avisa quando os dados foram atualizados depois de salvar", () => {
    const v = {
      id: "x",
      titulo: "t",
      url: "/",
      salvo_em: "",
      dados_ate: "2026-08-30",
    };
    expect(dadosAtualizados(v, "2026-09-27")).toBe(true);
    expect(dadosAtualizados(v, "2026-08-30")).toBe(false);
    expect(dadosAtualizados(v, undefined)).toBe(false);
  });

  it("lista corrompida não quebra a aplicação", () => {
    localStorage.setItem("sinalbr:analises", "{nao é json");
    expect(loadSaved()).toEqual([]);
  });
});

describe("cliente da API", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("repete parâmetros de lista e omite vazios", () => {
    const u = new URL(
      buildUrl("/v1/comparacao/perfil", {
        cd_ibge: [1, 2],
        meses: 12,
        categoria: undefined,
      }),
    );
    expect(u.searchParams.getAll("cd_ibge")).toEqual(["1", "2"]);
    expect(u.searchParams.has("categoria")).toBe(false);
  });

  it("falha de rede vira mensagem legível (não 'Failed to fetch')", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );
    const err = await analysis.qualidade().catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.message).toMatch(/Não foi possível conectar à API/);
    expect(err.status).toBeNull();
  });

  it("503 do pipeline mostra o detalhe explicando a etapa", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: "Rode a etapa: python -m sinalbr_data changes",
          }),
          { status: 503 },
        ),
      ),
    );
    const err = await analysis.radar({}).catch((e) => e);
    expect(err.status).toBe(503);
    expect(err.message).toMatch(/^Dados ainda não gerados: .*changes/);
  });
});

describe("CSV", () => {
  it("tem BOM, metadados e escapa vírgulas e aspas", () => {
    const csv = toCsv(
      ["a", "b"],
      [
        ["x,y", 'diz "oi"'],
        [null, 3],
      ],
      ["Fonte: teste"],
    );
    expect(csv.charCodeAt(0)).toBe(0xfeff);
    const lines = csv.slice(1).trim().split("\n");
    expect(lines).toEqual([
      "# Fonte: teste",
      "a,b",
      '"x,y","diz ""oi"""',
      ",3",
    ]);
  });
});

describe("componentes de estado", () => {
  it("Delta usa seta e texto, não só cor", () => {
    render(<Delta value={-12.5} />);
    expect(screen.getByText(/queda/)).toBeInTheDocument();
    expect(screen.getByText("▼")).toBeInTheDocument();
  });

  it("StateMessage de erro oferece nova tentativa", () => {
    const retry = vi.fn();
    render(<StateMessage error="falhou" onRetry={retry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("falhou");
    fireEvent.click(screen.getByRole("button", { name: "Tentar de novo" }));
    expect(retry).toHaveBeenCalled();
  });

  it("StateMessage vazio explica o motivo", () => {
    render(<StateMessage empty emptyText="Sem dados para este recorte." />);
    expect(
      screen.getByText("Sem dados para este recorte."),
    ).toBeInTheDocument();
  });
});
