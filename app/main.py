from fastapi import Request
from nicegui import app, ui

from app import pages  # noqa: F401  (rotas das páginas criadas na importação)
from app.database.repository.event import Event, EventList
from app.pages.layout import header, scroll_to_top


@app.on_connect
def start_app(): ...


def _periodo(event: Event) -> str:
    """Data do evento; eventos de vários dias mostram o intervalo."""
    inicio = event.data_hora_inicio.date()
    fim = event.data_hora_fim.date()
    if inicio == fim:
        return inicio.strftime("%d/%m/%Y")
    return f"{inicio:%d/%m/%Y} – {fim:%d/%m/%Y}"


def _event_card(event: Event) -> None:
    with (
        ui.link(target=f"/event/{event.id}").classes("no-underline text-inherit"),
        ui.card().tight().classes("w-full h-full cursor-pointer"),
    ):
        if event.banner_thumbnail:
            _ = ui.image(event.banner_thumbnail).classes("w-full aspect-video")
        else:
            # evento sem imagem: mantém a mesma proporção para alinhar o grid
            with ui.element("div").classes(
                "w-full aspect-video flex items-center justify-center bg-grey-4"
            ):
                _ = ui.icon("event", size="48px").classes("text-grey-7")
        with ui.card_section().classes("w-full"):
            _ = ui.label(event.nome).classes("text-subtitle1 text-weight-medium")
            with ui.row().classes("items-center gap-1 text-grey-7"):
                _ = ui.icon("calendar_today", size="16px")
                _ = ui.label(_periodo(event)).classes("text-body2")


@ui.page("/")
def index_page(request: Request):

    header(request)

    _ = ui.label("Eventos").classes("text-h5 q-mt-md")

    # 4 eventos por linha em telas largas; em telas menores o grid reduz as
    # colunas para os cards não ficarem espremidos
    @ui.refreshable
    def event_grid() -> None:
        if not events.items:
            _ = ui.label("Nenhum evento cadastrado.").classes("text-grey-7")
            return
        with ui.grid().classes("w-full gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4"):
            for event in events.items:
                _event_card(event)

    events = EventList(items=[], on_change=event_grid.refresh)
    event_grid()
    events.reload()

    scroll_to_top()


if __name__ in {
    "__main__",
    "__mp_main__",
}:  # mp_main é necessário por que o nicegui usa multiprocessing
    _ = ui.run(port=8000)
