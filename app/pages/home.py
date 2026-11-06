"""
Página inicial: a listagem de eventos em cartões e, para administradores, o
botão de criação de evento.
"""

from typing import Annotated

from fastapi import Depends
from nicegui import ui

from app.auth import eh_administrador, obter_usuario_opcional
from app.database.repository.event import listar_eventos
from app.database.repository.paginacao import EVENTOS_POR_PAGINA
from app.database.repository.user import Usuario
from app.pages.event import dialogo_criar_evento
from app.pages.layout import cartao_evento, pagina, paginacao


@pagina("/")
def pagina_inicial(
    usuario: Annotated[Usuario | None, Depends(obter_usuario_opcional)],
    page: int = 1,
):
    eh_admin = eh_administrador(usuario)
    resultado = listar_eventos(page)

    if resultado.num_pagina >= 1 and page != resultado.pagina_valida:
        # página fora dos limites (ex.: deletada entre navegações): volta à
        # última página existente, refletida também na URL
        ui.navigate.to(f"/?page={resultado.pagina_valida}")
        return

    with ui.row().classes("w-full items-center q-mt-md"):
        _ = ui.label("Eventos").classes("text-h5")
        if eh_admin:
            _ = ui.space()
            _ = ui.button(
                "Estatísticas",
                icon="insights",
                on_click=lambda: ui.navigate.to("/event/dashboard"),
            ).props("flat no-caps")
            _ = ui.button(
                "Criar evento",
                icon="add",
                on_click=lambda: dialogo_criar_evento(
                    lambda evento_id: ui.navigate.to(f"/event/{evento_id}")
                ),
            ).props("color=primary")

    # 4 eventos por linha em telas largas; em telas menores o grid reduz as
    # colunas para os cards não ficarem espremidos
    @ui.refreshable
    def grade_eventos() -> None:
        if resultado.total == 0:
            _ = ui.label("Nenhum evento cadastrado.").classes("text-grey-7")
            return
        with ui.grid().classes(
            "w-full gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4"
        ):
            for evento in resultado.itens:
                cartao_evento(evento)

    grade_eventos()

    paginacao(
        total=resultado.total,
        num_pagina=page,
        por_pagina=EVENTOS_POR_PAGINA,
        caminho="/",
    )
