"""
Painel administrativo de inscrições em eventos.

- ``/event/{evento_id}/registrations``: listagem das inscrições do evento
  (com destaque para as pendentes de avaliação).
- ``/event/{evento_id}/registrations/{usuario_id}``: avaliação — o
  administrador pode comentar (independentemente de aprovar/recusar),
  aprovar ou recusar. Um administrador não pode avaliar a própria inscrição.
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from nicegui import ui

from app.auth import exigir_administrador, obter_usuario
from app.database.repository.event import Evento, EventoNaoEncontrado, obter_evento
from app.database.repository.inscription_list import (
    listar_inscricoes_do_evento,
    obter_inscricao,
)
from app.database.repository.user import Usuario
from app.exceptions import (
    AprovacaoPropriaProibida,
    InscricaoNaoPendente,
)
from app.pages.layout import (
    dialogo_confirmacao,
    formatar_moeda,
    item_icone,
    meia_badge,
    nao_encontrado,
    pagina,
    status_badge,
    voltar_ao_topo,
)


# página privada + restrita a administradores
@pagina(
    "/event/{evento_id}/registrations",
    dependencies=[Depends(exigir_administrador)],
)
def pagina_inscricoes_do_evento(
    evento_id: int,
):
    try:
        evento: Evento = obter_evento(evento_id)
    except EventoNaoEncontrado:
        nao_encontrado(
            "event_busy", "Evento não encontrado", "/", "Voltar para a lista de eventos"
        )
        return

    with ui.column().classes("w-full gap-4").style("max-width: 1000px; margin: 0 auto"):
        with ui.row().classes("w-full items-center"):
            _ = ui.link(f"← {evento.nome}", f"/event/{evento.id}").classes(
                "text-primary"
            )

        _ = ui.label("Inscrições").classes("text-h5")

        @ui.refreshable
        def lista() -> None:
            inscricoes = listar_inscricoes_do_evento(evento_id)
            if not inscricoes:
                _ = ui.label("Nenhuma inscrição registrada.").classes("text-grey-7")
                return
            pendentes = sum(1 for i in inscricoes if i.status == "pendente")
            if pendentes:
                _ = ui.label(
                    f"{pendentes} inscrição(ões) aguardando avaliação."
                ).classes("text-warning text-body2")
            for inscricao in inscricoes:
                with (
                    ui.card().classes("w-full"),
                    ui.row().classes("w-full items-center gap-3"),
                ):
                    with ui.column().classes("gap-0 flex-grow"):
                        _ = ui.label(inscricao.usuario_nome).classes("text-subtitle1")
                        _ = ui.label(
                            f"Inscrito em {inscricao.data_inscricao:%d/%m/%Y %H:%M}"
                        ).classes("text-caption text-grey-7")
                    if inscricao.meia:
                        meia_badge()
                    if inscricao.valor:
                        _ = ui.label(formatar_moeda(inscricao.valor)).classes(
                            "text-body2"
                        )
                    status_badge(inscricao.status)
                    _ = ui.link(
                        "Avaliar",
                        f"/event/{evento.id}/registrations/{inscricao.usuario_id}",
                    ).props("flat dense no-caps color=primary")

        lista()

    voltar_ao_topo()


# página privada + restrita a administradores
@pagina(
    "/event/{evento_id}/registrations/{usuario_id}",
    dependencies=[Depends(exigir_administrador)],
)
def pagina_avaliacao(
    evento_id: int,
    usuario_id: int,
    usuario: Annotated[Usuario, Depends(obter_usuario)],
):
    try:
        evento: Evento = obter_evento(evento_id)
    except EventoNaoEncontrado:
        nao_encontrado(
            "event_busy", "Evento não encontrado", "/", "Voltar para a lista de eventos"
        )
        return

    inscricao = obter_inscricao(usuario_id, evento_id)

    with ui.column().classes("w-full gap-4").style("max-width: 1000px; margin: 0 auto"):
        _ = ui.link(
            f"← Inscrições de {evento.nome}",
            f"/event/{evento.id}/registrations",
        ).classes("text-primary")

        if inscricao is None:
            with ui.column().classes("w-full items-center q-mt-xl"):
                _ = ui.icon("assignment_late", size="64px").classes("text-grey-6")
                _ = ui.label("Inscrição não encontrada").classes("text-h6")
            return

        eh_proprio = usuario_id == usuario.id

        with ui.card().classes("w-full"), ui.column().classes("w-full gap-4"):
            with ui.row().classes("w-full items-center gap-3"):
                _ = ui.label(inscricao.usuario_nome or f"Usuário {usuario_id}").classes(
                    "text-h6"
                )
                status_badge(inscricao.status)
                _ = ui.space()
                _ = ui.link("Ver evento", f"/event/{evento.id}").props(
                    "flat dense no-caps"
                )

            with ui.row().classes("w-full items-center gap-x-6 gap-y-1 text-grey-8"):
                with item_icone("calendar_today"):
                    _ = ui.label(
                        f"Inscrito em {inscricao.data_inscricao:%d/%m/%Y %H:%M}"
                    ).classes("text-body2")
                with item_icone("attach_money"):
                    if evento.valor > 0:
                        _ = ui.label(formatar_moeda(inscricao.valor or 0.0)).classes(
                            "text-body2"
                        )
                        if inscricao.meia:
                            meia_badge()
                    else:
                        _ = ui.label("Gratuito").classes("text-body2 text-positive")

            if inscricao.comprovante_usuario is not None:
                with ui.row().classes("items-center gap-2"):
                    _ = ui.icon("picture_as_pdf", size="20px").classes("text-primary")
                    _ = ui.label("Comprovante").classes("text-caption text-grey-7")
                    _ = ui.link(
                        "Baixar comprovante",
                        f"/api/registrations/{evento.id}/{usuario_id}/comprovante",
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
                "Comentário", value=inscricao.comentario_administrador or ""
            ).classes("w-full")

            def salvar_comentario() -> None:
                inscricao.definir_comentario(comentario.value or "")
                ui.notify("Comentário salvo.", type="positive")

            _ = ui.button(
                "Salvar comentário",
                icon="save",
                on_click=salvar_comentario,
            ).props("outline")

            with ui.separator():
                pass

            if inscricao.status == "pendente":
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
                        def confirmar(fechar: Callable[[], None]) -> None:
                            try:
                                inscricao.aprovar(usuario.id)
                            except (
                                AprovacaoPropriaProibida,
                                InscricaoNaoPendente,
                            ) as e:
                                ui.notify(
                                    "Não foi possível aprovar a inscrição.",
                                    type="negative",
                                )
                                ui.log(f"Aprovar falhou: {e!r}")
                                return
                            ui.notify("Inscrição aprovada.", type="positive")
                            ui.navigate.to(f"/event/{evento_id}/registrations")

                        dialogo_confirmacao(
                            "Aprovar inscrição",
                            f"Confirmar a inscrição de {inscricao.usuario_nome or usuario_id} "
                            f"no valor de {formatar_moeda(inscricao.valor or 0.0)}?",
                            "Aprovar inscrição",
                            "positive",
                            confirmar,
                        )

                    def recusar() -> None:
                        def confirmar(fechar: Callable[[], None]) -> None:
                            try:
                                inscricao.recusar(usuario.id)
                            except (
                                AprovacaoPropriaProibida,
                                InscricaoNaoPendente,
                            ) as e:
                                ui.notify(
                                    "Não foi possível recusar a inscrição.",
                                    type="negative",
                                )
                                ui.log(f"Recusar falhou: {e!r}")
                                return
                            ui.notify("Inscrição recusada.", type="warning")
                            ui.navigate.to(f"/event/{evento_id}/registrations")

                        dialogo_confirmacao(
                            "Recusar inscrição",
                            f"Recusar a inscrição de {inscricao.usuario_nome or usuario_id} "
                            f"e liberar a vaga?",
                            "Recusar inscrição",
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
                    f"{inscricao.status})."
                ).classes("text-caption text-grey-7")

    voltar_ao_topo()
