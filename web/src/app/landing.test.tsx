import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Home from "@/app/page";

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...p
  }: {
    href: string;
    children: React.ReactNode;
  }) => (
    <a href={href} {...p}>
      {children}
    </a>
  ),
}));

describe("Landing", () => {
  it("tem um único h1, landmarks e link para o painel", () => {
    render(<Home />);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
    expect(
      screen.getAllByRole("link", { name: /painel/i }).length,
    ).toBeGreaterThan(0);
  });

  it("mostra as limitações (subnotificação e viés) na página", () => {
    render(<Home />);
    expect(screen.getByText(/subnotificação/)).toBeInTheDocument();
    expect(screen.getByText(/vieses de policiamento/)).toBeInTheDocument();
  });

  it("cobre as seções de problema, solução, impacto e privacidade", () => {
    const { container } = render(<Home />);
    for (const id of ["problema", "solucao", "impacto", "privacidade"]) {
      expect(container.querySelector(`#${id}`)).not.toBeNull();
    }
  });
});
