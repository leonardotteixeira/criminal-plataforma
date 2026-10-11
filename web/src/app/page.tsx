import Link from "next/link";
import { brand } from "@/config/brand";

// Landing provisória; a versão completa vem na Fase 4.
export default function Home() {
  return (
    <main className="mx-auto flex max-w-3xl flex-1 flex-col justify-center gap-6 px-6 py-24">
      <h1 className="text-4xl font-semibold tracking-tight">{brand.name}</h1>
      <p className="text-lg text-muted">{brand.tagline}.</p>
      <p>{brand.description}</p>
      <div>
        <Link
          href="/dashboard"
          className="inline-block rounded-md bg-accent px-5 py-2.5 font-medium text-white"
        >
          Abrir painel
        </Link>
      </div>
    </main>
  );
}
