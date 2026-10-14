from fastapi import Depends
from nicegui import app, ui

from app import pages  # noqa: F401  (rotas das páginas criadas na importação)
from app.auth import cookie_manager


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


# accesível somente para usuários logados
@ui.page("/", dependencies=[Depends(cookie_manager)])
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

    with ui.page_scroller(position="bottom-right", x_offset=20, y_offset=20):
        _ = ui.button("Voltar ao topo")


if __name__ in {
    "__main__",
    "__mp_main__",
}:  # mp_main é necessário por que o nicegui usa multiprocessing
    _ = ui.run(port=8000)
