"""
Página de detalhes de um evento: banner, nome, descrição, data, localização,
valor, vagas disponíveis e a programação de atividades.

A página é pública: a seção de inscrição se adapta ao estado do usuário
(não logado, já inscrito, evento lotado) e abre um dialog para escolher
valor cheio ou meia-entrada e anexar o comprovante.
"""

from datetime import datetime
from typing import Annotated

from fastapi import Depends
from nicegui import events, ui
from nicegui.elements.upload_files import FileUpload

from app.auth import get_optional_current_user
from app.database.repository.activity import Activity, get_event_activities
from app.database.repository.event import Event, get_event
from app.database.repository.inscription_list import (
    get_inscription,
    register_user_for_event,
)
from app.database.repository.user import User
from app.exceptions import (
    AgeBelowClassification,
    DuplicateEventRegistration,
    EventHasDependencies,
    EventHasInscriptions,
    EventNotFound,
    InscriptionProofNotPdf,
    InvalidActivitySchedule,
    NoMoreVacancy,
    VacancyBelowInscriptions,
)
from app.pages.event_form import (
    campos_evento,
    coletar_valores,
    conectar_validacao_evento,
    valores_evento,
)
from app.pages.layout import formatar_moeda, page, scroll_to_top, upload_comprovante


def _data_hora(dt: datetime) -> str:
    return dt.strftime("%d/%m/%Y às %H:%M")


def _info(icon: str, titulo: str) -> ui.column:
    """Linha de informação com ícone; o conteúdo é adicionado pelo chamador."""
    with ui.row().classes("items-start no-wrap gap-3"):
        _ = ui.icon(icon, size="24px").classes("text-primary")
        coluna = ui.column().classes("gap-0")
        with coluna:
            _ = ui.label(titulo).classes("text-caption text-grey-7")
    return coluna


def _vagas(event: Event) -> None:
    disponiveis = max(event.vagas - (event.inscritas or 0), 0)
    with _info("event_seat", "Vagas"):
        if disponiveis == 0:
            _ = ui.label(f"Esgotado ({event.vagas} vagas)").classes("text-negative")
        else:
            _ = ui.label(f"{disponiveis} de {event.vagas} disponíveis")


def _valor(event: Event) -> None:
    with _info("attach_money", "Valor"):
        if event.valor > 0:
            _ = ui.label(f"Cheio: {formatar_moeda(event.valor)}")
            _ = ui.label(
                f"Meia-entrada: {formatar_moeda(round(event.valor / 2, 2))}"
            ).classes("text-grey-7")
        else:
            _ = ui.label("Evento gratuito").classes("text-positive")


def _localizacao(event: Event) -> None:
    if event.latitude is None or event.longitude is None:
        _ = ui.label("Não informada").classes("text-grey-7")
        return
    # os tiles do mapa são carregados do OpenStreetMap pelo navegador
    mapa = ui.leaflet(center=(event.latitude, event.longitude), zoom=15).classes(
        "w-full h-64 rounded-borders"
    )
    _ = mapa.marker(latlng=(event.latitude, event.longitude))


def _horario_atividade(activity: Activity) -> str:
    inicio, fim = activity.data_hora_inicio, activity.data_hora_fim
    return f"{_data_hora(inicio)} – {_data_hora(fim)}"


def _activity_card(activity: Activity) -> None:
    with ui.card().classes("w-full"), ui.column().classes("w-full gap-2"):
        _ = ui.link(
            activity.nome,
            f"/event/{activity.id_evento}/activities/{activity.id}",
        ).classes("text-h6 text-weight-medium no-underline text-inherit")
        with ui.row().classes("items-center gap-x-6 gap-y-1 text-grey-8"):
            for icon, texto in (
                ("schedule", _horario_atividade(activity)),
                ("meeting_room", activity.sala),
                ("event_seat", f"{activity.vagas} vagas"),
            ):
                with ui.row().classes("items-center gap-1"):
                    _ = ui.icon(icon, size="18px")
                    _ = ui.label(texto).classes("text-body2")
        if activity.descricao:
            _ = ui.label(activity.descricao).classes("text-body1")

        # página pública: dos ministrantes só são exibidos dados de
        # apresentação, nunca CPF ou e-mail
        _ = ui.label("Ministrantes").classes("text-caption text-grey-7 q-mt-sm")
        for lecturer in activity.lecturers:
            with ui.row().classes("items-start no-wrap gap-2"):
                _ = ui.icon("person", size="20px").classes("text-primary")
                with ui.column().classes("gap-0"):
                    with ui.row().classes("items-center gap-2"):
                        _ = ui.label(lecturer.user.nome).classes("text-weight-medium")
                        _ = ui.label(lecturer.instituicao).classes("text-grey-7")
                        if lecturer.link_lattes:
                            _ = ui.link("Lattes", lecturer.link_lattes, new_tab=True)
                    if lecturer.mini_bio:
                        _ = ui.label(lecturer.mini_bio).classes(
                            "text-body2 text-grey-8"
                        )


def _atividades(event_id: int) -> None:
    activities = get_event_activities(event_id)
    with ui.row().classes("w-full items-center"):
        _ = ui.label("Atividades").classes("text-h5")
        _ = ui.space()
        _ = ui.link(
            "Ver todas as atividades",
            f"/event/{event_id}/activities",
        ).props("flat dense no-caps color=primary")
    if not activities:
        _ = ui.label("Nenhuma atividade cadastrada.").classes("text-grey-7")
        return
    for activity in activities:
        _activity_card(activity)


def _dialogo_inscricao(event: Event, user: User) -> None:
    """
    Dialog de inscrição: o usuário escolhe valor cheio ou meia-entrada e
    anexa o comprovante (que também justifica a meia-entrada). O valor é
    derivado do preço do evento — o usuário nunca digita o valor.

    Evento gratuito não tem nem escolha de valor nem comprovante.
    """
    gratuita = event.valor == 0
    meia_preco = round(event.valor / 2, 2)
    arquivo: FileUpload | None = None

    def file_change(e: events.UploadEventArguments):
        nonlocal arquivo
        arquivo = e.file
        erro_comprovante.visible = False

    with ui.dialog() as dialogo, ui.card().classes("w-full").style("max-width: 500px"):
        _ = ui.label(f"Inscrever-se em {event.nome}").classes("text-h6")

        radios = None
        if gratuita:
            _ = ui.label("Este evento é gratuito, é só confirmar a inscrição.").classes(
                "text-body2 text-grey-7 q-mb-md"
            )
        else:
            radios = ui.radio(
                {
                    "cheio": f"Valor cheio — {formatar_moeda(event.valor)}",
                    "meia": f"Meia-entrada — {formatar_moeda(meia_preco)}",
                },
                value="cheio",
            ).classes("w-full q-mb-md")

            _ = ui.label(
                "Comprovante de pagamento em pdf, para a meia-entrada inclua um documento válido no mesmo arquivo"
            ).classes("text-caption text-grey-7")

            _ = upload_comprovante(on_upload=file_change)
            erro_comprovante = ui.label(
                "Anexe o comprovante em PDF para confirmar a inscrição."
            ).classes("text-negative text-caption")
            erro_comprovante.visible = False

        async def enviar() -> None:
            if not gratuita and not arquivo:
                erro_comprovante.visible = True
                return
            try:
                _ = register_user_for_event(
                    user_id=user.id,
                    event_id=event.id,
                    meia=radios.value == "meia" if radios else False,
                    comprovante_usuario=await arquivo.read() if arquivo else None,
                )
            except DuplicateEventRegistration:
                ui.notify("Você já possui uma inscrição neste evento.")
                return
            except AgeBelowClassification:
                ui.notify(f"""
                Sua idade não permite a inscrição neste evento
                (classificação {event.classificacao_indicativa}+)
                """)
                return
            except NoMoreVacancy:
                ui.notify("As vagas deste evento acabaram.")
                return
            except InscriptionProofNotPdf:
                ui.notify("O comprovante precisa ser um arquivo PDF.")
                return
            ui.navigate.to(f"/user/registrations/{event.id}")

        with ui.row().classes("w-full"):
            _ = ui.space()
            _ = ui.button("Voltar", on_click=dialogo.close).props("flat")
            _ = ui.button("Inscrever-se", on_click=enviar).props("color=primary")

    dialogo.open()


def _secao_inscricao(event: Event, user: User | None) -> None:
    """Botão de inscrição adaptado ao estado do usuário."""
    with ui.card().classes("w-full"), ui.row().classes("w-full items-center gap-3"):
        _ = ui.icon("how_to_reg", size="28px").classes("text-primary")
        if user is None:
            _ = ui.label("Faça login para se inscrever neste evento.").classes(
                "text-body1"
            )
            _ = ui.space()
            _ = ui.link("Entrar", "/login").props("flat dense no-caps color=primary")
            return

        existente = get_inscription(user.id, event.id)
        if existente is not None and existente.status != "cancelada":
            _ = ui.label(f"Sua inscrição está {existente.status.lower()}.").classes(
                "text-body1"
            )
            _ = ui.space()
            _ = ui.link(
                "Ver minha inscrição",
                f"/user/registrations/{event.id}",
            ).props("flat dense no-caps color=primary")
            return

        if existente is not None:  # cancelada: não é possível re-inscrever (PK)
            _ = ui.label("Sua inscrição neste evento foi cancelada.").classes(
                "text-body1"
            )
            _ = ui.space()
            _ = ui.link(
                "Ver detalhes",
                f"/user/registrations/{event.id}",
            ).props("flat dense no-caps color=primary")
            return

        if (event.inscritas or 0) >= event.vagas:
            _ = ui.button("Evento lotado", icon="event_busy").props("outline").disable()
            return

        _ = ui.label("Garanta sua vaga").classes("text-body1")
        _ = ui.space()
        _ = ui.button(
            "Inscrever-se",
            icon="how_to_reg",
            on_click=lambda: _dialogo_inscricao(event, user),
        ).props("color=primary")


def _dialogo_editar_evento(event: Event) -> None:
    """
    Dialog administrativo de edição de evento, pré-preenchido.

    O salvamento delega as regras de negócio ao ``Event.update``: vagas não
    podem ficar abaixo das inscrições ativas e o novo horário precisa
    continuar contendo as atividades existentes.
    """
    with ui.dialog() as dialogo, ui.card().classes("w-full").style("max-width: 900px"):
        _ = ui.label(f"Editar {event.nome}").classes("text-h6")
        form = campos_evento(valores_evento(event))
        # validações de múltiplos campos (datas e lat/lng) exibidas inline
        conectar_validacao_evento(form)
        if (event.inscritas or 0) > 0:
            _ = ui.label(
                f"Evento com {event.inscritas} inscrição(ões) ativa(s): "
                "as vagas não podem ficar abaixo desse número."
            ).classes("text-caption text-grey-7")

        def salvar() -> None:
            # validações de servidor: erros aparecem nos próprios campos
            valores = coletar_valores(form)
            if valores is None:
                return
            try:
                event.update(
                    nome=valores.nome,
                    descricao=valores.descricao,
                    data_hora_inicio=valores.data_hora_inicio,
                    data_hora_fim=valores.data_hora_fim,
                    classificacao_indicativa=valores.classificacao_indicativa,
                    vagas=valores.vagas,
                    latitude=valores.latitude,
                    longitude=valores.longitude,
                    valor=valores.valor,
                    banner=valores.banner,
                    banner_thumbnail=valores.banner_thumbnail,
                )
            except VacancyBelowInscriptions:
                ui.notify(
                    "As vagas não podem ficar menores que o número de "
                    "inscrições ativas.",
                    type="negative",
                )
                return
            except InvalidActivitySchedule:
                ui.notify(
                    "O novo horário precisa continuar contendo as atividades "
                    "do evento.",
                    type="negative",
                )
                return
            except DuplicateEventRegistration:
                ui.notify("Já existe um evento com esse nome.", type="negative")
                return
            dialogo.close()
            ui.notify("Evento atualizado.", type="positive")
            ui.navigate.to(f"/event/{event.id}")

        with ui.row().classes("w-full q-mt-md"):
            _ = ui.space()
            _ = ui.button("Cancelar", on_click=dialogo.close).props("flat")
            _ = ui.button("Salvar", on_click=salvar).props("color=primary")

    dialogo.open()


def _confirmar_exclusao(event: Event) -> None:
    """
    Dialog de confirmação da exclusão de um evento.

    A exclusão é bloqueada quando o evento possui ao menos uma inscrição
    (regra de negócio); sem inscrições, as atividades e os ministrantes são
    excluídos junto.
    """
    with ui.dialog() as dialogo, ui.card().classes("w-full").style("max-width: 420px"):
        _ = ui.label("Excluir este evento?").classes("text-h6")
        _ = ui.label(
            "As atividades e os ministrantes do evento também serão "
            "excluídos. Esta ação não pode ser desfeita."
        ).classes("text-body2 text-grey-7")

        def confirmar() -> None:
            try:
                removido = event.delete()
            except EventHasInscriptions:
                ui.notify(
                    "Este evento possui usuários inscritos e não pode ser excluído.",
                    type="negative",
                )
                return
            except EventHasDependencies:
                ui.notify("Não foi possível excluir o evento.", type="negative")
                return
            if not removido:
                ui.notify("Evento não encontrado.", type="warning")
                return
            dialogo.close()
            ui.notify("Evento excluído.", type="positive")
            ui.navigate.to("/")

        with ui.row().classes("w-full q-mt-md"):
            _ = ui.space()
            _ = ui.button("Voltar", on_click=dialogo.close).props("flat")
            _ = ui.button("Excluir", on_click=confirmar).props("color=negative")

    dialogo.open()


# página pública: não exige login
@page("/event/{event_id}")
def event_page(
    event_id: int,
    user: Annotated[User | None, Depends(get_optional_current_user)],
):
    try:
        event = get_event(event_id)
    except EventNotFound:
        with ui.column().classes("w-full items-center q-mt-xl"):
            _ = ui.icon("event_busy", size="64px").classes("text-grey-6")
            _ = ui.label("Evento não encontrado").classes("text-h6")
            _ = ui.link("Voltar para a lista de eventos", "/")
        return

    eh_admin = user is not None and user.papel == "administrador"

    with ui.column().classes("w-full gap-4").style("max-width: 1000px; margin: 0 auto"):
        with ui.row().classes("w-full items-center gap-1"):
            _ = ui.link("← Eventos", "/").classes("text-primary")
            if eh_admin:
                _ = ui.space()
                _ = ui.link(
                    "Inscrições",
                    f"/event/{event.id}/registrations",
                ).props("flat dense no-caps")

        if event.banner:
            _ = (
                ui.image(event.banner)
                .classes("w-full rounded-borders")
                .style("aspect-ratio: 3 / 1")
            )
        if eh_admin:
            with ui.row().classes("w-full items-center gap-1"):
                _ = ui.label(event.nome).classes("text-h4")
                _ = ui.space()
                _ = ui.button(
                    "Editar",
                    icon="edit",
                    on_click=lambda: _dialogo_editar_evento(event),
                ).props("flat dense no-caps")

        _ = ui.label(event.descricao or "").classes("text-body1")

        _secao_inscricao(event, user)

        _atividades(event.id)

        with ui.card().classes("w-full"), ui.column().classes("w-full gap-4"):
            with _info("schedule", "Data"):
                _ = ui.label(f"Início: {_data_hora(event.data_hora_inicio)}")
                _ = ui.label(f"Fim: {_data_hora(event.data_hora_fim)}")
            _vagas(event)
            _valor(event)
            _localizacao(event)
        if eh_admin:
            with ui.row().classes("w-full items-center gap-1"):
                _ = ui.space()
                _ = ui.button(
                    "Excluir",
                    icon="delete",
                    on_click=lambda: _confirmar_exclusao(event),
                ).props("dense no-caps color=negative ")
                _ = ui.space()

    scroll_to_top()
