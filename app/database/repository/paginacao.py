"""
Auxiliares de paginação das consultas de listagem.

As consultas de listagem recebem ``num_pagina`` e ``por_pagina`` e devolvem
``Pagina[T]``: os itens da página e o total de linhas da consulta inteira (o
total vem de um ``COUNT`` separado, com o mesmo filtro). A camada de
interface usa ``total`` para desenhar o paginador e mostrar "X–Y de Z".
"""

from collections.abc import Iterator
from dataclasses import dataclass
from math import ceil
from typing import Generic, TypeVar

# múltiplo de 4 (grid de eventos em telas largas) e de 2 (telas menores)
EVENTOS_POR_PAGINA = 8
# demais listagens (cartões verticais)
LISTAS_POR_PAGINA = 10

T = TypeVar("T")


@dataclass(frozen=True)
class Pagina(Generic[T]):
    """
    Página de uma consulta de listagem: ``itens`` da página ``num_pagina``,
    com ``total`` contado sobre a consulta inteira (mesmo filtro, sem
    ``LIMIT``/``OFFSET``).
    """

    itens: list[T]
    total: int
    num_pagina: int
    por_pagina: int

    @property
    def total_paginas(self) -> int:
        """Número de páginas da consulta; ao menos 1 (mesmo sem itens)."""
        return max(1, ceil(self.total / self.por_pagina))

    @property
    def pagina_valida(self) -> int:
        """``num_pagina`` limitado às páginas existentes."""
        return min(max(self.num_pagina, 1), self.total_paginas)


def limites(num_pagina: int, por_pagina: int) -> tuple[int, int]:
    """
    ``(limite, deslocamento)`` da cláusula ``LIMIT``/``OFFSET``; páginas
    menores que 1 contam como a primeira.
    """
    pagina = max(num_pagina, 1)
    return por_pagina, (pagina - 1) * por_pagina


def janela(
    total: int, num_pagina: int, por_pagina: int
) -> Iterator[tuple[int, int]]:
    """
    Intervalo ``[índice_inicial, índice_final]`` (1-based) dos itens da
    página, para o texto "Mostrando X–Y de Z"; nada em páginas vazias.
    """
    pagina = max(num_pagina, 1)
    inicio = (pagina - 1) * por_pagina + 1
    fim = min(inicio + por_pagina, total + 1)
    if inicio <= total:
        yield inicio, fim - 1
