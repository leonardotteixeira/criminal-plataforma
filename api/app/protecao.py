"""Controles de divulgação estatística aplicados pela API. Ver docs/privacidade.md.

1. k-mínimo: valores abaixo de K_MIN nunca são publicados.
2. Agregação consistente: um total "todos os crimes" é a soma das categorias que seriam
   publicadas isoladamente (cada uma >= K_MIN no mesmo recorte). Assim, "total menos categorias
   exibidas" é sempre zero e não revela a categoria suprimida (supressão complementar).
3. Arredondamento de hexágonos: contagens por célula viram múltiplos de CELL_ROUND.
4. Janelas ancoradas nos hexágonos: só 3, 6, 12 ou 24 meses terminando na data dos dados, para
   impedir isolar um único mês por diferença entre janelas arbitrárias.
"""

from datetime import date

from fastapi import HTTPException

from .settings import CELL_ROUND, K_MIN

JANELAS_MESES = (3, 6, 12, 24)


def agregado(
    tabela: str, chaves: list[str], where: str, params: list, categoria: str | None
) -> tuple[str, list]:
    """Subconsulta (chaves..., n) com agregação consistente entre categorias.

    Com categoria: soma direta. Sem categoria: soma só as combinações (chaves, categoria) que
    atingem K_MIN no recorte, ou seja, exatamente o que seria publicado categoria a categoria.
    """
    k = ", ".join(chaves)
    if categoria:
        return (
            f"SELECT {k}, sum(n) AS n FROM {tabela} WHERE {where} AND categoria = ? GROUP BY {k}",
            [*params, categoria],
        )
    return (
        f"""SELECT {k}, sum(n) AS n FROM (
              SELECT {k}, categoria, sum(n) AS n FROM {tabela} WHERE {where}
              GROUP BY {k}, categoria HAVING sum(n) >= {K_MIN}
            ) GROUP BY {k}""",
        list(params),
    )


def meses_entre(inicio: date, fim: date) -> int:
    return (fim.year - inicio.year) * 12 + fim.month - inicio.month + 1


def janela_ancorada(inicio: date | None, fim: date | None, dados_ate: date) -> tuple[date, date]:
    """Valida a janela dos endpoints por hexágono: termina em dados_ate e dura 3/6/12/24 meses."""
    if fim is not None and fim != dados_ate:
        raise HTTPException(
            422,
            f"Para hexágonos, a janela deve terminar na data dos dados ({dados_ate}). "
            "Janelas arbitrárias permitiriam isolar contagens pequenas por diferença.",
        )
    if inicio is None:
        inicio = date(dados_ate.year - 1, dados_ate.month, 1)
        inicio = date(inicio.year + (inicio.month == 12), inicio.month % 12 + 1, 1)
    inicio = inicio.replace(day=1)
    n = meses_entre(inicio, dados_ate)
    if n not in JANELAS_MESES:
        raise HTTPException(
            422,
            f"Para hexágonos, use janelas de {', '.join(map(str, JANELAS_MESES))} meses terminando em "
            f"{dados_ate} (recebido: {n} meses).",
        )
    return inicio, dados_ate


def arredondar_celula(n: int) -> int:
    """Arredonda a contagem de um hexágono para o múltiplo de CELL_ROUND mais próximo (mín. k).

    Aplicado depois do teste k-mínimo, sobre o total do filtro. Combinado com as janelas
    ancoradas, a diferença entre janelas não recupera contagens pequenas exatas.
    """
    if CELL_ROUND <= 1:
        return n
    return max(K_MIN, CELL_ROUND * round(n / CELL_ROUND))


def publicar(n: int | None) -> int | None:
    """Valor publicável (>= K_MIN) ou None (suprimido). Zero real continua zero."""
    if n is None or n == 0:
        return 0 if n == 0 else None
    return int(n) if n >= K_MIN else None
