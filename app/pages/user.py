"""
Páginas das inscrições do usuário autenticado.

- ``/user/events``: listagem das inscrições do usuário (inclui a prévia das
  pendentes, com o status de cada uma).
- ``/user/registrations/{evento_id}``: detalhes da inscrição, com edição
  (meia-entrada/comprovante) e cancelamento, sempre com confirmação.
- ``/user/events/{evento_id}/attendances``: presenças do usuário em um
  evento.
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from nicegui import events, ui
from nicegui.elements.upload_files import FileUpload

from app.auth import obter_usuario
from app.database.repository.event import Evento, EventoNaoEncontrado, obter_evento
from app.database.repository.inscription import InscricaoEvento
from app.database.repository.inscription_list import obter_inscricao
from app.database.repository.user import Usuario
from app.exceptions import (
    ComprovanteNaoEhPdf,
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
    upload_comprovante,
    voltar_ao_topo,
)


def _dialogo_edicao(evento: Evento, inscricao: InscricaoEvento) -> None:
    """
    Edita uma inscrição **pendente**: trocar valor cheio/meia-entrada e (de
    modo opcional) substituir o comprovante. O valor é derivado do preço do
    evento; o usuário nunca digita o valor.
    """
    gratuita = evento.valor == 0

    with ui.dialog() as dialogo, ui.card().classes("w-full").style("max-width: 500px"):
        _ = ui.label(f"Editar inscrição — {evento.nome}").classes("text-h6")

        radios = None
        arquivo: FileUpload | None = None

        def arquivo_selecionado(e: events.UploadEventArguments):
            nonlocal arquivo
            arquivo = e.file
            erro.visible = False

        if gratuita:
            _ = ui.label(
                "Este evento é gratuito: não há valor ou comprovante para editar."
            ).classes("text-body2 text-grey-7 q-mb-md")
        else:
            radios = ui.radio(
                {
                    "cheio": f"Valor cheio — {formatar_moeda(evento.valor)}",
                    "meia": f"Meia-entrada — {formatar_moeda(evento.valor_meia)}",
                },
                value="meia" if inscricao.meia else "cheio",
            ).classes("w-full q-mb-md")

            if inscricao.comprovante_usuario is not None:
                _ = ui.label(
                    "Comprovante atual (anexe um novo para substituir):"
                ).classes("text-caption text-grey-7")
                _ = ui.link(
                    "Baixar comprovante atual",
                    f"/api/registrations/{evento.id}/{inscricao.usuario_id}/comprovante",
                ).props("flat dense no-caps")

            _ = ui.label("Novo comprovante (PDF, opcional)").classes(
                "text-caption text-grey-7 q-mt-sm"
            )
            erro = ui.label().classes("text-negative q-mb-md")
            erro.visible = False
            _ = upload_comprovante(arquivo_selecionado)

        async def salvar() -> None:
            meia = radios.value == "meia" if radios else False
            novo_comprovante = (
                (await arquivo.read()) if arquivo else inscricao.comprovante_usuario
            )
            if evento.valor > 0 and novo_comprovante is None:
                erro.set_text("É necessário um comprovante para inscrição paga.")
                erro.visible = True
                return
            erro.visible = False
            try:
                inscricao.atualizar(
                    meia=meia,
                    valor=evento.valor_meia if meia else evento.valor,
                    comprovante_usuario=novo_comprovante,
                )
            except InscricaoNaoPendente:
                ui.notify(
                    "Esta inscrição já não está pendente; o administrador a avaliou."
                )
                return
            except ComprovanteNaoEhPdf:
                ui.notify("O comprovante precisa ser um arquivo PDF.")
                return
            ui.navigate.to(f"/user/registrations/{evento.id}")

        with ui.row().classes("w-full"):
            _ = ui.space()
            _ = ui.button("Cancelar", on_click=dialogo.close).props("flat")
            if not gratuita:
                _ = ui.button("Salvar", on_click=salvar).props("color=primary")

    dialogo.open()


def _confirmar_cancelamento(evento_id: int, ao_cancelar: Callable[[], None]) -> None:
    """Dialog de confirmação antes de cancelar a inscrição (regra de negócio)."""

    def confirmar(fechar: Callable[[], None]) -> None:
        ao_cancelar()
        ui.navigate.to(f"/user/registrations/{evento_id}")

    dialogo_confirmacao(
        "Cancelar esta inscrição?",
        "A vaga será liberada para outros usuários. Esta ação não pode ser desfeita.",
        "Cancelar inscrição",
        "negative",
        confirmar,
        rotulo_cancelar="Manter inscrição",
    )


# página privada: exige sessão válida
@pagina("/user/events")
def pagina_minhas_inscricoes(usuario: Annotated[Usuario, Depends(obter_usuario)]):
    with ui.column().classes("w-full gap-4").style("max-width: 1000px; margin: 0 auto"):
        _ = ui.label("Minhas inscrições").classes("text-h5 q-mt-md")

        inscricoes = usuario.listar_inscricoes()
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
            for inscricao in inscricoes:
                with (
                    ui.card().classes("w-full"),
                    ui.row().classes("w-full items-center gap-3"),
                ):
                    with ui.column().classes("gap-0 flex-grow"):
                        _ = ui.link(
                            inscricao.evento_nome,
                            f"/event/{inscricao.evento_id}",
                        ).classes("text-subtitle1 no-underline text-inherit")
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
                        "Detalhes",
                        f"/user/registrations/{inscricao.evento_id}",
                    ).props("flat dense no-caps color=primary")
                    _ = ui.link(
                        "Presenças",
                        f"/user/events/{inscricao.evento_id}/attendances",
                    ).props("flat dense no-caps color=primary")

    voltar_ao_topo()


@pagina("/user/registrations/{evento_id}")
def pagina_inscricao(
    evento_id: int,
    usuario: Annotated[Usuario, Depends(obter_usuario)],
):
    # somente o dono da inscrição pode ver a página
    inscricao = obter_inscricao(usuario.id, evento_id)

    with ui.column().classes("w-full gap-4").style("max-width: 1000px; margin: 0 auto"):
        _ = ui.link("← Minhas inscrições", "/user/events").classes("text-primary")

        if inscricao is None:
            nao_encontrado(
                "assignment_late",
                "Inscrição não encontrada",
                "/user/events",
                "Voltar para minhas inscrições",
            )
            return

        try:
            evento = obter_evento(evento_id)
        except EventoNaoEncontrado:
            nao_encontrado(
                "assignment_late",
                "Inscrição não encontrada",
                "/user/events",
                "Voltar para minhas inscrições",
            )
            return

        with ui.card().classes("w-full"), ui.column().classes("w-full gap-4"):
            with ui.row().classes("w-full items-center gap-3"):
                _ = ui.label(evento.nome).classes("text-h6")
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
                        f"/api/registrations/{evento.id}/{usuario.id}/comprovante",
                    ).props("flat dense no-caps color=primary")

            if inscricao.comentario_administrador:
                with ui.column().classes("w-full gap-1 rounded-borders p-4 bg-grey-2"):
                    _ = ui.label("Comentário do administrador").classes(
                        "text-caption text-grey-7"
                    )
                    _ = ui.label(inscricao.comentario_administrador).classes(
                        "text-body2"
                    )

            with ui.row().classes("w-full"):
                if inscricao.status == "pendente":
                    _ = ui.label("Aguardando avaliação do administrador.").classes(
                        "text-caption text-grey-7"
                    )
                    _ = ui.space()
                    if evento.valor > 0:
                        _ = ui.button(
                            "Editar",
                            icon="edit",
                            on_click=lambda: _dialogo_edicao(evento, inscricao),
                        ).props("outline")
                    _ = ui.button(
                        "Cancelar inscrição",
                        icon="cancel",
                        on_click=lambda: _confirmar_cancelamento(
                            evento_id, inscricao.cancelar
                        ),
                    ).props("color=negative outline")
                elif inscricao.status == "confirmada":
                    _ = ui.label("Inscrição confirmada. Boa participação!").classes(
                        "text-caption text-positive"
                    )
                    _ = ui.space()
                    _ = ui.button(
                        "Cancelar inscrição",
                        icon="cancel",
                        on_click=lambda: _confirmar_cancelamento(
                            evento_id, inscricao.cancelar
                        ),
                    ).props("color=negative outline")
                else:  # cancelada
                    _ = ui.label(
                        "Inscrição cancelada — não é possível reativá-la."
                    ).classes("text-caption text-grey-7")

    voltar_ao_topo()


# página privada: exige sessão válida
@pagina("/user/events/{evento_id}/attendances")
def pagina_presencas(
    evento_id: int,
    usuario: Annotated[Usuario, Depends(obter_usuario)],
):
    """
    Presenças do usuário em um evento (regra de negócio): lista as
    atividades em que ele esteve presente, marcadas por um administrador.
    """
    try:
        evento = obter_evento(evento_id)
    except EventoNaoEncontrado:
        nao_encontrado(
            "event_busy",
            "Evento não encontrado",
            "/user/events",
            "Voltar para minhas inscrições",
        )
        return

    presencas = usuario.listar_presencas(evento_id)

    with ui.column().classes("w-full gap-4").style("max-width: 1000px; margin: 0 auto"):
        _ = ui.link(f"← {evento.nome}", f"/user/registrations/{evento_id}").classes(
            "text-primary"
        )

        _ = ui.label("Minhas presenças").classes("text-h5 q-mt-md")

        if not presencas:
            with (
                ui.card().classes("w-full"),
                ui.column().classes("w-full gap-2 items-center"),
            ):
                _ = ui.icon("event_note", size="48px").classes("text-grey-5")
                _ = ui.label(
                    "Você não tem presenças registradas neste evento."
                ).classes("text-grey-7")
                _ = ui.link("Ver evento", f"/event/{evento.id}").props(
                    "flat dense no-caps color=primary"
                )
        else:
            for presenca in presencas:
                with (
                    ui.card().classes("w-full"),
                    ui.row().classes("w-full items-center gap-3"),
                ):
                    _ = ui.icon("event_available", size="24px").classes("text-positive")
                    with ui.column().classes("gap-0 flex-grow"):
                        _ = ui.label(presenca.atividade_nome).classes("text-subtitle1")
                        _ = ui.label(f"Sala {presenca.sala}").classes(
                            "text-caption text-grey-7"
                        )
                    _ = ui.link(
                        "Ver atividade",
                        f"/event/{presenca.evento_id}/activities/{presenca.id_atividade}",
                    ).props("flat dense no-caps color=primary")

    voltar_ao_topo()
