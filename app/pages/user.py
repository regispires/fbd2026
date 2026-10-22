"""
Páginas das inscrições do usuário autenticado.

- ``/user/events``: listagem das inscrições do usuário (inclui a prévia das
  pendentes, com o status de cada uma).
- ``/user/registrations/{event_id}``: detalhes da inscrição, com edição
  (meia-entrada/comprovante) e cancelamento, sempre com confirmação.
"""

from typing import Annotated

from fastapi import Depends, Request
from nicegui import events, ui
from nicegui.elements.upload_files import FileUpload

from app.auth import get_current_user
from app.database.repository.event import Event, get_event
from app.database.repository.inscription import EventInscription
from app.database.repository.inscription_list import get_inscription
from app.database.repository.user import User
from app.exceptions import (
    EventNotFound,
    InscriptionNotPending,
    InscriptionProofNotPdf,
)
from app.pages.layout import (
    formatar_moeda,
    header,
    meia_badge,
    scroll_to_top,
    status_badge,
    upload_comprovante,
)


def _dialogo_edicao(event: Event, inscription: EventInscription) -> None:
    """
    Edita uma inscrição **pendente**: trocar valor cheio/meia-entrada e (de
    modo opcional) substituir o comprovante. O valor é derivado do preço do
    evento; o usuário nunca digita o valor.
    """
    gratuita = event.valor == 0
    meia_preco = round(event.valor / 2, 2)

    with ui.dialog() as dialogo, ui.card().classes("w-full").style("max-width: 500px"):
        _ = ui.label(f"Editar inscrição — {event.nome}").classes("text-h6")

        radios = None
        arquivo: FileUpload | None = None

        def file_change(e: events.UploadEventArguments):
            nonlocal arquivo
            arquivo = e.file

        if gratuita:
            _ = ui.label(
                "Este evento é gratuito: não há valor ou comprovante para editar."
            ).classes("text-body2 text-grey-7 q-mb-md")
        else:
            radios = ui.radio(
                {
                    "cheio": f"Valor cheio — {formatar_moeda(event.valor)}",
                    "meia": f"Meia-entrada — {formatar_moeda(meia_preco)}",
                },
                value="meia" if inscription.meia else "cheio",
            ).classes("w-full q-mb-md")

            if inscription.comprovante_usuario is not None:
                _ = ui.label(
                    "Comprovante atual (anexe um novo para substituir):"
                ).classes("text-caption text-grey-7")
                _ = ui.link(
                    "Baixar comprovante atual",
                    f"/api/registrations/{event.id}/{inscription.user_id}/comprovante",
                ).props("flat dense no-caps")

            _ = ui.label("Novo comprovante (PDF, opcional)").classes(
                "text-caption text-grey-7 q-mt-sm"
            )
            erro = ui.label().classes("text-negative q-mb-md")
            erro.visible = False
            _ = upload_comprovante(file_change)

        async def salvar() -> None:
            meia = radios.value == "meia" if radios else False
            novo_comprovante = (
                (await arquivo.read()) if arquivo else inscription.comprovante_usuario
            )
            if event.valor > 0 and novo_comprovante is None:
                ui.notify("É necessário um comprovante para inscrição paga.")
                return
            try:
                inscription.update(
                    meia=meia,
                    valor=meia_preco if meia else event.valor,
                    comprovante_usuario=novo_comprovante,
                )
            except InscriptionNotPending:
                ui.notify(
                    "Esta inscrição já não está pendente; o administrador a avaliou."
                )
                return
            except InscriptionProofNotPdf:
                ui.notify("O comprovante precisa ser um arquivo PDF.")
                return
            ui.navigate.to(f"/user/registrations/{event.id}")

        with ui.row().classes("w-full"):
            _ = ui.space()
            _ = ui.button("Cancelar", on_click=dialogo.close).props("flat")
            if not gratuita:
                _ = ui.button("Salvar", on_click=salvar).props("color=primary")

    dialogo.open()


def _confirmar_cancelamento(event_id: int, ao_cancelar) -> None:
    """Dialog de confirmação antes de cancelar a inscrição (regra de negócio)."""
    with ui.dialog() as dialogo, ui.card().classes("w-full").style("max-width: 420px"):
        _ = ui.label("Cancelar esta inscrição?").classes("text-h6")
        _ = ui.label(
            "A vaga será liberada para outros usuários. Esta ação não pode ser desfeita."
        ).classes("text-body2 text-grey-7")
        with ui.row().classes("w-full q-mt-md"):
            _ = ui.space()
            _ = ui.button("Manter inscrição", on_click=dialogo.close).props("flat")

            def confirmar() -> None:
                ao_cancelar()
                ui.navigate.to(f"/user/registrations/{event_id}")

            _ = ui.button("Cancelar inscrição", on_click=confirmar).props(
                "color=negative"
            )

    dialogo.open()


def _nao_encontrada() -> None:
    with ui.column().classes("w-full items-center q-mt-xl"):
        _ = ui.icon("assignment_late", size="64px").classes("text-grey-6")
        _ = ui.label("Inscrição não encontrada").classes("text-h6")
        _ = ui.link("Voltar para minhas inscrições", "/user/events")


# página privada: exige sessão válida
@ui.page("/user/events")
def user_events_page(
    request: Request, user: Annotated[User, Depends(get_current_user)]
):
    header(request)

    with ui.column().classes("w-full gap-4").style("max-width: 1000px; margin: 0 auto"):
        _ = ui.label("Minhas inscrições").classes("text-h5 q-mt-md")

        inscricoes = user.get_event_inscriptions()
        if not inscricoes:
            with (
                ui.card().classes("w-full"),
                ui.column().classes("w-full gap-2 items-center"),
            ):
                _ = ui.icon("assignment_late", size="48px").classes("text-grey-5")
                _ = ui.label("Você ainda não se inscreveu em nenhum evento.").classes(
                    "text-grey-7"
                )
                _ = ui.link("Ver eventos", "/").props(
                    "flat dense no-caps color=primary"
                )
        else:
            for inscription in inscricoes:
                with (
                    ui.card().classes("w-full"),
                    ui.row().classes("w-full items-center gap-3"),
                ):
                    with ui.column().classes("gap-0 flex-grow"):
                        _ = ui.link(
                            inscription.event_nome,
                            f"/event/{inscription.event_id}",
                        ).classes("text-subtitle1 no-underline text-inherit")
                        _ = ui.label(
                            f"Inscrito em {inscription.data_inscricao:%d/%m/%Y %H:%M}"
                        ).classes("text-caption text-grey-7")
                    if inscription.meia:
                        meia_badge()
                    if inscription.valor:
                        _ = ui.label(formatar_moeda(inscription.valor)).classes(
                            "text-body2"
                        )
                    status_badge(inscription.status)
                    _ = ui.link(
                        "Detalhes",
                        f"/user/registrations/{inscription.event_id}",
                    ).props("flat dense no-caps color=primary")

    scroll_to_top()


@ui.page("/user/registrations/{event_id}")
def user_registration_page(
    request: Request,
    event_id: int,
    user: Annotated[User, Depends(get_current_user)],
):
    header(request)

    # somente o dono da inscrição pode ver a página
    inscription = get_inscription(user.id, event_id)

    with ui.column().classes("w-full gap-4").style("max-width: 1000px; margin: 0 auto"):
        _ = ui.link("← Minhas inscrições", "/user/events").classes("text-primary")

        if inscription is None:
            _nao_encontrada()
            return

        try:
            event = get_event(event_id)
        except EventNotFound:
            _nao_encontrada()
            return

        with ui.card().classes("w-full"), ui.column().classes("w-full gap-4"):
            with ui.row().classes("w-full items-center gap-3"):
                _ = ui.label(event.nome).classes("text-h6")
                status_badge(inscription.status)
                _ = ui.space()
                _ = ui.link("Ver evento", f"/event/{event.id}").props(
                    "flat dense no-caps"
                )

            with ui.row().classes("w-full items-center gap-x-6 gap-y-1 text-grey-8"):
                with ui.row().classes("items-center gap-1"):
                    _ = ui.icon("calendar_today", size="18px")
                    _ = ui.label(
                        f"Inscrito em {inscription.data_inscricao:%d/%m/%Y %H:%M}"
                    ).classes("text-body2")
                with ui.row().classes("items-center gap-1"):
                    _ = ui.icon("attach_money", size="18px")
                    if event.valor > 0:
                        _ = ui.label(formatar_moeda(inscription.valor or 0.0)).classes(
                            "text-body2"
                        )
                        if inscription.meia:
                            meia_badge()
                    else:
                        _ = ui.label("Gratuito").classes("text-body2 text-positive")

            if inscription.comprovante_usuario is not None:
                with ui.row().classes("items-center gap-2"):
                    _ = ui.icon("picture_as_pdf", size="20px").classes("text-primary")
                    _ = ui.label("Comprovante").classes("text-caption text-grey-7")
                    _ = ui.link(
                        "Baixar comprovante",
                        f"/api/registrations/{event.id}/{user.id}/comprovante",
                    ).props("flat dense no-caps color=primary")

            if inscription.comentario_administrador:
                with ui.column().classes("w-full gap-1 rounded-borders p-4 bg-grey-2"):
                    _ = ui.label("Comentário do administrador").classes(
                        "text-caption text-grey-7"
                    )
                    _ = ui.label(inscription.comentario_administrador).classes(
                        "text-body2"
                    )

            with ui.row().classes("w-full"):
                if inscription.status == "pendente":
                    _ = ui.label("Aguardando avaliação do administrador.").classes(
                        "text-caption text-grey-7"
                    )
                    _ = ui.space()
                    if event.valor > 0:
                        _ = ui.button(
                            "Editar",
                            icon="edit",
                            on_click=lambda: _dialogo_edicao(event, inscription),
                        ).props("outline")
                    _ = ui.button(
                        "Cancelar inscrição",
                        icon="cancel",
                        on_click=lambda: _confirmar_cancelamento(
                            event_id, inscription.cancel
                        ),
                    ).props("color=negative outline")
                elif inscription.status == "confirmada":
                    _ = ui.label("Inscrição confirmada. Boa participação!").classes(
                        "text-caption text-positive"
                    )
                    _ = ui.space()
                    _ = ui.button(
                        "Cancelar inscrição",
                        icon="cancel",
                        on_click=lambda: _confirmar_cancelamento(
                            event_id, inscription.cancel
                        ),
                    ).props("color=negative outline")
                else:  # cancelada
                    _ = ui.label(
                        "Inscrição cancelada — não é possível reativá-la."
                    ).classes("text-caption text-grey-7")

    scroll_to_top()
