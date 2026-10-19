"""
Página de detalhes de um evento: banner, nome, descrição, data, localização,
vagas disponíveis e a programação de atividades.
"""

from datetime import datetime

from fastapi import Request
from nicegui import ui

from app.database.repository.activity import Activity, get_event_activities
from app.database.repository.event import Event, get_event
from app.exceptions import EventNotFound
from app.pages.layout import header, scroll_to_top


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


def _localizacao(event: Event) -> None:
    with _info("place", "Localização"):
        if event.latitude is None or event.longitude is None:
            _ = ui.label("Não informada").classes("text-grey-7")
            return
        _ = ui.label(f"{event.latitude:.4f}, {event.longitude:.4f}")
    # os tiles do mapa são carregados do OpenStreetMap pelo navegador
    mapa = ui.leaflet(center=(event.latitude, event.longitude), zoom=15).classes(
        "w-full h-64 rounded-borders"
    )
    _ = mapa.marker(latlng=(event.latitude, event.longitude))


def _horario_atividade(activity: Activity) -> str:
    inicio, fim = activity.data_hora_inicio, activity.data_hora_fim
    if inicio.date() == fim.date():
        return f"{inicio:%d/%m/%Y}, {inicio:%H:%M} – {fim:%H:%M}"
    return f"{_data_hora(inicio)} – {_data_hora(fim)}"


def _activity_card(activity: Activity) -> None:
    with ui.card().classes("w-full"), ui.column().classes("w-full gap-2"):
        _ = ui.label(activity.nome).classes("text-h6")
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
                        _ = ui.label(lecturer.mini_bio).classes("text-body2 text-grey-8")


def _atividades(event_id: int) -> None:
    activities = get_event_activities(event_id)
    _ = ui.label("Atividades").classes("text-h5 q-mt-md")
    if not activities:
        _ = ui.label("Nenhuma atividade cadastrada.").classes("text-grey-7")
        return
    for activity in activities:
        _activity_card(activity)


# página pública: não exige login
@ui.page("/event/{event_id}")
def event_page(event_id: int, request: Request):
    header(request)

    try:
        event = get_event(event_id)
    except EventNotFound:
        with ui.column().classes("w-full items-center q-mt-xl"):
            _ = ui.icon("event_busy", size="64px").classes("text-grey-6")
            _ = ui.label("Evento não encontrado").classes("text-h6")
            _ = ui.link("Voltar para a lista de eventos", "/")
        return

    with ui.column().classes("w-full gap-4").style("max-width: 1000px; margin: 0 auto"):
        _ = ui.link("← Eventos", "/").classes("text-primary")

        if event.banner:
            _ = ui.image(event.banner).classes("w-full rounded-borders").style(
                "aspect-ratio: 3 / 1"
            )

        _ = ui.label(event.nome).classes("text-h4")
        if event.descricao:
            _ = ui.label(event.descricao).classes("text-body1")

        _atividades(event.id)

        with ui.card().classes("w-full"), ui.column().classes("w-full gap-4"):
            with _info("schedule", "Data"):
                _ = ui.label(f"Início: {_data_hora(event.data_hora_inicio)}")
                _ = ui.label(f"Fim: {_data_hora(event.data_hora_fim)}")
            _vagas(event)
            _localizacao(event)

    scroll_to_top()
