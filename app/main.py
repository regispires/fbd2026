from fastapi import Depends
from nicegui import app, ui

from app import pages  # noqa: F401  (rotas das páginas criadas na importação)
from app.auth import cookie_manager
from app.database.repository.event import Event, EventList


@app.on_connect
def start_app(): ...


def _sair() -> None:
    """
    Logout: o fetch é uma requisição real do navegador, então o
    ``Set-Cookie`` de expiração da resposta limpa o cookie no navegador.
    """

    ui.run_javascript(
        """
        fetch('/api/logout', {method: 'POST'}).then(r => {
            window.location.assign(r.redirected ? r.url : '/login');
        });
        """
    )


def _periodo(event: Event) -> str:
    """Data do evento; eventos de vários dias mostram o intervalo."""
    inicio = event.data_hora_inicio.date()
    fim = event.data_hora_fim.date()
    if inicio == fim:
        return inicio.strftime("%d/%m/%Y")
    return f"{inicio:%d/%m/%Y} – {fim:%d/%m/%Y}"


def _event_card(event: Event) -> None:
    with ui.card().tight().classes("w-full"):
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


# accesível somente para usuários logados
@ui.page("/")
def index_page():

    with ui.header(bordered=True, elevated=True).style(
        "display: flex; align-items: center;"
    ):
        _ = ui.label("Exemplo FBD - Gestão de Eventos").style("font-size:150%")

        _ = ui.space()
        with (
            ui.icon("account_circle").props("size=32px").classes("cursor-pointer"),
            ui.menu(),
        ):
            with ui.menu_item("Tema Escuro", auto_close=False):
                with ui.item_section().props("avatar"):
                    dark_enabled = ui.dark_mode()
                    _ = ui.icon("dark_mode")
                _ = ui.switch().bind_value(dark_enabled).props("dense color=accent")

            with (
                ui.menu_item("Sair", on_click=_sair),
                ui.item_section().props("avatar"),
            ):
                _ = ui.icon("logout")

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

    with ui.page_scroller(position="bottom-right", x_offset=20, y_offset=20):
        _ = ui.button("Voltar ao topo")


if __name__ in {
    "__main__",
    "__mp_main__",
}:  # mp_main é necessário por que o nicegui usa multiprocessing
    _ = ui.run(port=8000)
