import Link from "next/link";
import { ThemeToggle } from "@/components/ThemeToggle";
import { HexPattern } from "@/components/landing/HexPattern";
import { brand, stats } from "@/config/brand";

const NAV = [
  ["Problema", "#problema"],
  ["Solução", "#solucao"],
  ["Impacto", "#impacto"],
  ["Privacidade", "#privacidade"],
] as const;

const PROBLEMAS = [
  {
    t: "Dados enormes e dispersos",
    d: "Cada ano de ocorrências da SSP-SP é uma planilha de ~200 MB, com mais de 1 milhão de linhas. Sem tratamento, comparar territórios e períodos é inviável para a maioria das pessoas.",
  },
  {
    t: "Formatos que mudam",
    d: "O layout dos arquivos muda entre anos (colunas renomeadas, campos que somem). Séries históricas confiáveis exigem normalização cuidadosa e auditável.",
  },
  {
    t: "Qualidade desigual",
    d: "Cerca de 30% dos registros não informam a hora e ~28% não têm coordenada utilizável. Sem medir isso, qualquer mapa passa uma precisão que não existe.",
  },
];

const SOLUCOES = [
  {
    t: "Mapa de calor",
    d: "Ocorrências por hexágono (~0,7 km²) e tipo de crime, com filtros de período e legenda acessível.",
  },
  {
    t: "Padrões no tempo",
    d: "Tendência, sazonalidade e horário/dia da semana, sempre sobre períodos completos para não confundir atraso de registro com queda.",
  },
  {
    t: "Radar territorial",
    d: "O que mudou e merece investigação: mudanças persistentes descontado o movimento do estado, variações fora do padrão e picos semanais, cada um com o critério que o fez aparecer.",
    href: "/radar",
  },
  {
    t: "Comparação entre municípios",
    d: "Até quatro municípios lado a lado, em taxas por 100 mil habitantes, com intervalo de incerteza e exportação em CSV.",
    href: "/comparar",
  },
  {
    t: "Previsão com prestação de contas",
    d: "Registros esperados nas próximas 4 semanas, comparados a baselines simples em backtest sem vazamento. Mostramos inclusive onde o modelo não ganha.",
  },
  {
    t: "Qualidade dos dados à vista",
    d: "Cobertura por ano e tipo de crime, semanas incompletas e histórico de processamento, para saber quanto confiar em cada análise.",
    href: "/qualidade",
  },
];

const PRIVACIDADE = [
  [
    "Só dados abertos",
    "SSP-SP e IBGE. Nada de bases restritas, nomes, CPFs, placas ou endereços.",
  ],
  [
    "Minimização na entrada",
    "Logradouro, número e número do BO são descartados já na leitura; as coordenadas viram só um hexágono.",
  ],
  [
    "Agregação e k-mínimo",
    `Células, municípios e pontos de série com menos de ${stats.kMin} ocorrências nunca são exibidos.`,
  ],
  [
    "Sem vigilância",
    "O produto não identifica nem permite identificar pessoas, e não deve ser usado para decisões sobre indivíduos.",
  ],
];

function Section({
  id,
  title,
  eyebrow,
  children,
}: {
  id: string;
  title: string;
  eyebrow: string;
  children: React.ReactNode;
}) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-t`}
      className="scroll-mt-16 py-16 sm:py-24"
    >
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <p className="text-sm font-medium uppercase tracking-wider text-accent">
          {eyebrow}
        </p>
        <h2
          id={`${id}-t`}
          className="mt-2 max-w-3xl text-3xl font-semibold tracking-tight sm:text-4xl"
        >
          {title}
        </h2>
        <div className="mt-10">{children}</div>
      </div>
    </section>
  );
}

export default function Home() {
  return (
    <>
      <a
        href="#conteudo"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded focus:bg-surface focus:px-3 focus:py-2"
      >
        Ir para o conteúdo
      </a>
      <header className="sticky top-0 z-40 border-b border-border bg-background/85 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
          <Link href="/" className="text-lg font-semibold tracking-tight">
            {brand.name}
          </Link>
          <nav
            aria-label="Seções"
            className="hidden gap-6 text-sm text-muted md:flex"
          >
            {NAV.map(([l, h]) => (
              <a key={h} href={h} className="hover:text-foreground">
                {l}
              </a>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <Link
              href="/dashboard"
              className="rounded-md bg-accent px-4 py-1.5 text-sm font-medium text-background"
            >
              Abrir painel
            </Link>
          </div>
        </div>
      </header>

      <main id="conteudo" className="flex-1">
        <section aria-labelledby="hero-t" className="overflow-hidden">
          <div className="mx-auto grid max-w-6xl items-center gap-10 px-4 py-16 sm:px-6 sm:py-24 lg:grid-cols-2">
            <div>
              <p className="text-sm font-medium text-accent">
                Inteligência criminal aberta · piloto São Paulo
              </p>
              <h1
                id="hero-t"
                className="mt-3 text-4xl font-semibold leading-tight tracking-tight sm:text-5xl"
              >
                Mais clareza sobre segurança pública, sem expor ninguém.
              </h1>
              <p className="mt-5 max-w-xl text-lg text-muted">
                {brand.name} reúne dados abertos de ocorrências em um painel que
                mostra onde, quando e quanto, com os limites de cada número à
                vista.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Link
                  href="/dashboard"
                  className="rounded-md bg-accent px-5 py-2.5 font-medium text-background"
                >
                  Explorar o painel
                </Link>
                <a
                  href="#privacidade"
                  className="rounded-md border border-border px-5 py-2.5 font-medium hover:bg-surface"
                >
                  Como protegemos a privacidade
                </a>
              </div>
              <dl className="mt-10 grid max-w-md grid-cols-3 gap-4">
                {[
                  [stats.registros, `registros, ${stats.periodo}`],
                  [stats.municipios, "municípios de SP"],
                  [`k ≥ ${stats.kMin}`, "ocorrências por célula exibida"],
                ].map(([v, l]) => (
                  <div key={l}>
                    <dt className="sr-only">{l}</dt>
                    <dd className="text-2xl font-semibold tabular-nums">{v}</dd>
                    <dd className="text-xs text-muted">{l}</dd>
                  </div>
                ))}
              </dl>
            </div>
            <HexPattern className="mx-auto w-full max-w-lg" />
          </div>
        </section>

        <div className="border-y border-border bg-surface">
          <Section
            id="problema"
            eyebrow="O problema"
            title="A informação existe, mas está fragmentada e difícil de usar."
          >
            <div className="grid gap-4 md:grid-cols-3">
              {PROBLEMAS.map((p) => (
                <article
                  key={p.t}
                  className="rounded-lg border border-border bg-background p-6"
                >
                  <h3 className="font-semibold">{p.t}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted">
                    {p.d}
                  </p>
                </article>
              ))}
            </div>
          </Section>
        </div>

        <Section
          id="solucao"
          eyebrow="A solução"
          title="Um pipeline auditável e um painel que explica seus próprios limites."
        >
          <div className="grid gap-4 sm:grid-cols-2">
            {SOLUCOES.map((s, i) => (
              <article
                key={s.t}
                className="rounded-lg border border-border bg-surface p-6"
              >
                <span className="text-sm font-medium tabular-nums text-accent">
                  0{i + 1}
                </span>
                <h3 className="mt-1 font-semibold">{s.t}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted">{s.d}</p>
                {"href" in s && s.href && (
                  <Link
                    href={s.href}
                    className="mt-3 inline-block text-sm font-medium text-accent hover:underline"
                  >
                    Abrir →
                  </Link>
                )}
              </article>
            ))}
          </div>
          <ol
            className="mt-10 flex flex-wrap items-center gap-2 text-sm text-muted"
            aria-label="Fluxo dos dados"
          >
            {[
              "SSP-SP e IBGE",
              "Bronze: colunas mínimas",
              "Silver: limpeza e H3",
              "Gold: agregados",
              "API e painel",
            ].map((s, i, a) => (
              <li key={s} className="flex items-center gap-2">
                <span className="rounded-full border border-border bg-surface px-3 py-1">
                  {s}
                </span>
                {i < a.length - 1 && <span aria-hidden="true">→</span>}
              </li>
            ))}
          </ol>
        </Section>

        <div className="border-y border-border bg-surface">
          <Section
            id="impacto"
            eyebrow="Impacto"
            title="O que o piloto já mostra, e o que ele não promete."
          >
            <p className="max-w-3xl text-muted">
              Este é um projeto independente de portfólio, sem clientes ou uso
              operacional. Os resultados abaixo vêm dos dados reais da SSP-SP e
              estão documentados com método.
            </p>
            <div className="mt-8 grid gap-4 md:grid-cols-3">
              {[
                [
                  "−20,3%",
                  "Registros de roubo no estado nos últimos 12 meses completos vs. os 12 anteriores. É variação de registros, não necessariamente de crime.",
                ],
                [
                  "14–18%",
                  "Redução do erro de contagem do modelo de previsão frente a uma média simples de 12 semanas, em backtest sem vazamento.",
                ],
                [
                  "< 0,5 p.p.",
                  "Ganho do modelo em apontar QUAIS áreas concentram mais ocorrências: os pontos quentes são muito persistentes e uma média simples já os encontra.",
                ],
              ].map(([v, d]) => (
                <article
                  key={v}
                  className="rounded-lg border border-border bg-background p-6"
                >
                  <p className="text-3xl font-semibold tabular-nums">{v}</p>
                  <p className="mt-2 text-sm leading-relaxed text-muted">{d}</p>
                </article>
              ))}
            </div>
          </Section>
        </div>

        <Section
          id="privacidade"
          eyebrow="Segurança e privacidade"
          title="Anonimização por design, não como remendo."
        >
          <ul className="grid gap-4 sm:grid-cols-2">
            {PRIVACIDADE.map(([t, d]) => (
              <li
                key={t}
                className="flex gap-4 rounded-lg border border-border bg-surface p-6"
              >
                <span
                  aria-hidden="true"
                  className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full bg-accent"
                />
                <div>
                  <h3 className="font-semibold">{t}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-muted">{d}</p>
                </div>
              </li>
            ))}
          </ul>
          <div
            role="note"
            className="mt-8 rounded-lg border border-amber-500/60 bg-amber-500/10 p-6 text-sm leading-relaxed"
          >
            <h3 className="font-semibold">
              Limitações que você precisa conhecer
            </h3>
            <ul className="mt-2 list-disc space-y-1 pl-5">
              <li>
                Boletins de ocorrência refletem o <strong>registro</strong>, não
                o crime real: há subnotificação.
              </li>
              <li>
                Modelos preditivos podem reforçar vieses de policiamento. Use
                para entender padrões, nunca para decidir sobre pessoas.
              </li>
              <li>
                Os meses mais recentes são parciais por atraso de registro.
              </li>
            </ul>
          </div>
        </Section>

        <section
          aria-labelledby="cta-t"
          className="border-t border-border bg-surface"
        >
          <div className="mx-auto flex max-w-6xl flex-col items-start gap-4 px-4 py-16 sm:px-6 md:flex-row md:items-center md:justify-between">
            <h2
              id="cta-t"
              className="max-w-xl text-2xl font-semibold tracking-tight"
            >
              Veja os dados de São Paulo no mapa, com todos os avisos à vista.
            </h2>
            <Link
              href="/dashboard"
              className="rounded-md bg-accent px-6 py-3 font-medium text-background"
            >
              Abrir painel
            </Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-border py-8 text-sm text-muted">
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <p>
            {brand.name} é um projeto independente, sem vínculo com órgãos de
            segurança. Fontes: {brand.dataSource}. Marca provisória.
          </p>
        </div>
      </footer>
    </>
  );
}
