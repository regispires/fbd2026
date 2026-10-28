"""
Página inicial: a listagem de eventos em cartões e, para administradores, o
botão de criação de evento.
"""

from typing import Annotated

from fastapi import Depends
from nicegui import ui

from app.auth import eh_administrador, obter_usuario_opcional
from app.database.repository.event import listar_eventos
from app.database.repository.user import Usuario
from app.pages.event import dialogo_criar_evento
from app.pages.layout import cartao_evento, pagina


@pagina("/")
def pagina_inicial(
    usuario: Annotated[Usuario | None, Depends(obter_usuario_opcional)],
):
    eh_admin = eh_administrador(usuario)

    with ui.row().classes("w-full items-center q-mt-md"):
        _ = ui.label("Eventos").classes("text-h5")
        if eh_admin:
            _ = ui.space()
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
        eventos = listar_eventos()
        if not eventos:
            _ = ui.label("Nenhum evento cadastrado.").classes("text-grey-7")
            return
        with ui.grid().classes(
            "w-full gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4"
        ):
            for evento in eventos:
                cartao_evento(evento)

    grade_eventos()
