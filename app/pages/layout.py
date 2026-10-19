"""
Elementos compartilhados entre as páginas (cabeçalho, botão de voltar ao topo).
"""

from fastapi import Request
from nicegui import ui

from app.auth import COOKIE_NAME, cookie_manager


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


def header(request: Request) -> None:
    """
    Cabeçalho com o título (link para a página inicial) e o menu do usuário.

    As páginas que o usam são públicas, então o menu mostra "Sair" quando a
    requisição traz um cookie de sessão válido e "Entrar" caso contrário.
    """
    logado = cookie_manager.verificar_sessao(request.cookies.get(COOKIE_NAME))
    with ui.header(bordered=True, elevated=True).style(
        "display: flex; align-items: center;"
    ):
        _ = (
            ui.link("Exemplo FBD - Gestão de Eventos", "/")
            .classes("text-white no-underline")
            .style("font-size:150%")
        )

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

            if logado:
                with (
                    ui.menu_item("Sair", on_click=_sair),
                    ui.item_section().props("avatar"),
                ):
                    _ = ui.icon("logout")
            else:
                with (
                    ui.menu_item("Entrar", on_click=lambda: ui.navigate.to("/login")),
                    ui.item_section().props("avatar"),
                ):
                    _ = ui.icon("login")


def scroll_to_top() -> None:
    with ui.page_scroller(position="bottom-right", x_offset=20, y_offset=20):
        _ = ui.button("Voltar ao topo")
