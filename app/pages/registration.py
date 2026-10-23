"""
Painel administrativo de inscrições em eventos.

- ``/event/{event_id}/registrations``: listagem das inscrições do evento
  (com destaque para as pendentes de avaliação).
- ``/event/{event_id}/registrations/{user_id}``: avaliação — o administrador
  pode comentar (independentemente de aprovar/recusar), aprovar ou recusar.
  Um administrador não pode avaliar a própria inscrição.
"""

from typing import Annotated

from fastapi import Depends
from nicegui import ui

from app.auth import get_current_user, require_administrador
from app.database.repository.event import Event, get_event
from app.database.repository.inscription_list import InscriptionList, get_inscription
from app.database.repository.user import User
from app.exceptions import (
    CannotApproveOwnInscription,
    EventNotFound,
    InscriptionNotPending,
)
from app.pages.layout import (
    formatar_moeda,
    meia_badge,
    page,
    scroll_to_top,
    status_badge,
)


def _evento_nao_encontrado() -> None:
    with ui.column().classes("w-full items-center q-mt-xl"):
        _ = ui.icon("event_busy", size="64px").classes("text-grey-6")
        _ = ui.label("Evento não encontrado").classes("text-h6")
        _ = ui.link("Voltar para a lista de eventos", "/")


def _confirmar_acao(titulo: str, mensagem: str, cor: str, on_click) -> None:
    """Dialog de confirmação para aprovar/recusar (ações irreversíveis)."""
    with ui.dialog() as dialogo, ui.card().classes("w-full").style("max-width: 420px"):
        _ = ui.label(titulo).classes("text-h6")
        _ = ui.label(mensagem).classes("text-body2 text-grey-7")
        with ui.row().classes("w-full q-mt-md"):
            _ = ui.space()
            _ = ui.button("Voltar", on_click=dialogo.close).props("flat")
            _ = ui.button(titulo, on_click=on_click).props(f"color={cor}")

    dialogo.open()


# página privada + restrita a administradores
@page(
    "/event/{event_id}/registrations",
    dependencies=[Depends(require_administrador)],
)
def admin_registrations_page(
    event_id: int,
    user: Annotated[User, Depends(get_current_user)],
):
    try:
        event: Event = get_event(event_id)
    except EventNotFound:
        _evento_nao_encontrado()
        return

    with ui.column().classes("w-full gap-4").style("max-width: 1000px; margin: 0 auto"):
        with ui.row().classes("w-full items-center"):
            _ = ui.link(f"← {event.nome}", f"/event/{event.id}").classes("text-primary")

        _ = ui.label("Inscrições").classes("text-h5")

        @ui.refreshable
        def lista() -> None:
            if not inscricoes.items:
                _ = ui.label("Nenhuma inscrição registrada.").classes("text-grey-7")
                return
            pendentes = sum(1 for i in inscricoes.items if i.status == "pendente")
            if pendentes:
                _ = ui.label(
                    f"{pendentes} inscrição(ões) aguardando avaliação."
                ).classes("text-warning text-body2")
            for i in inscricoes.items:
                with (
                    ui.card().classes("w-full"),
                    ui.row().classes("w-full items-center gap-3"),
                ):
                    with ui.column().classes("gap-0 flex-grow"):
                        _ = ui.label(i.user_nome).classes("text-subtitle1")
                        _ = ui.label(
                            f"Inscrito em {i.data_inscricao:%d/%m/%Y %H:%M}"
                        ).classes("text-caption text-grey-7")
                    if i.meia:
                        meia_badge()
                    if i.valor:
                        _ = ui.label(formatar_moeda(i.valor)).classes("text-body2")
                    status_badge(i.status)
                    _ = ui.link(
                        "Avaliar",
                        f"/event/{event.id}/registrations/{i.user_id}",
                    ).props("flat dense no-caps color=primary")

        inscricoes = InscriptionList(
            items=[], on_change=lista.refresh, event_id=event_id
        )
        lista()
        inscricoes.reload()

    scroll_to_top()


@page(
    "/event/{event_id}/registrations/{user_id}",
    dependencies=[Depends(require_administrador)],
)
def admin_registration_detail_page(
    event_id: int,
    user_id: int,
    user: Annotated[User, Depends(get_current_user)],
):
    try:
        event: Event = get_event(event_id)
    except EventNotFound:
        _evento_nao_encontrado()
        return

    inscription = get_inscription(user_id, event_id)

    with ui.column().classes("w-full gap-4").style("max-width: 1000px; margin: 0 auto"):
        _ = ui.link(
            f"← Inscrições de {event.nome}",
            f"/event/{event.id}/registrations",
        ).classes("text-primary")

        if inscription is None:
            with ui.column().classes("w-full items-center q-mt-xl"):
                _ = ui.icon("assignment_late", size="64px").classes("text-grey-6")
                _ = ui.label("Inscrição não encontrada").classes("text-h6")
            return

        eh_proprio = user_id == user.id

        with ui.card().classes("w-full"), ui.column().classes("w-full gap-4"):
            with ui.row().classes("w-full items-center gap-3"):
                _ = ui.label(inscription.user_nome or f"Usuário {user_id}").classes(
                    "text-h6"
                )
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
                        f"/api/registrations/{event.id}/{user_id}/comprovante",
                    ).props("flat dense no-caps color=primary")
            else:
                _ = ui.label("Sem comprovante anexado.").classes(
                    "text-caption text-grey-7"
                )

            # comentário: independente de aprovar/recusar (regra de negócio)
            _ = ui.label("Comentário do administrador").classes(
                "text-caption text-grey-7"
            )
            comentario = ui.textarea(
                "Comentário", value=inscription.comentario_administrador or ""
            ).classes("w-full")

            def salvar_comentario() -> None:
                inscription.set_comentario(comentario.value or "")
                ui.notify("Comentário salvo.", type="positive")

            _ = ui.button(
                "Salvar comentário",
                icon="save",
                on_click=salvar_comentario,
            ).props("outline")

            with ui.separator():
                pass

            if inscription.status == "pendente":
                if eh_proprio:
                    _ = ui.label(
                        "Esta é a sua própria inscrição: você não pode aprovar nem recusá-la. "
                        "Peça para outro administrador avaliar."
                    ).classes("text-warning text-body2")
                else:
                    _ = ui.label(
                        "Avalie o comprovante e o pedido de meia-entrada (se houver):"
                    ).classes("text-caption text-grey-7")

                    def aprovar() -> None:
                        def confirmar() -> None:
                            try:
                                inscription.approve(user.id)
                            except (
                                CannotApproveOwnInscription,
                                InscriptionNotPending,
                            ) as e:
                                ui.notify(
                                    "Não foi possível aprovar a inscrição.",
                                    type="negative",
                                )
                                ui.log(f"Aprovar falhou: {e!r}")
                                return
                            ui.notify("Inscrição aprovada.", type="positive")
                            ui.navigate.to(f"/event/{event_id}/registrations")

                        _confirmar_acao(
                            "Aprovar inscrição",
                            f"Confirmar a inscrição de {inscription.user_nome or user_id} "
                            f"no valor de {formatar_moeda(inscription.valor or 0.0)}?",
                            "positive",
                            confirmar,
                        )

                    def recusar() -> None:
                        def confirmar() -> None:
                            try:
                                inscription.reject(user.id)
                            except (
                                CannotApproveOwnInscription,
                                InscriptionNotPending,
                            ) as e:
                                ui.notify(
                                    "Não foi possível recusar a inscrição.",
                                    type="negative",
                                )
                                ui.log(f"Recusar falhou: {e!r}")
                                return
                            ui.notify("Inscrição recusada.", type="warning")
                            ui.navigate.to(f"/event/{event_id}/registrations")

                        _confirmar_acao(
                            "Recusar inscrição",
                            f"Recusar a inscrição de {inscription.user_nome or user_id} "
                            f"e liberar a vaga?",
                            "negative",
                            confirmar,
                        )

                    with ui.row().classes("w-full"):
                        _ = ui.space()
                        _ = ui.button("Recusar", icon="cancel", on_click=recusar).props(
                            "color=negative outline"
                        )
                        _ = ui.button("Aprovar", icon="check", on_click=aprovar).props(
                            "color=positive"
                        )
            else:
                _ = ui.label(
                    "Esta inscrição já foi avaliada (status atual: "
                    f"{inscription.status})."
                ).classes("text-caption text-grey-7")

    scroll_to_top()
