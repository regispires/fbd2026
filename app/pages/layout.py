"""
Elementos compartilhados entre as páginas (cabeçalho, badges, formatação de
moeda, upload de comprovante, botão de voltar ao topo).
"""

from collections.abc import Callable

from fastapi import Request
from nicegui import events, ui
from nicegui.elements.upload_files import FileUpload

from app.auth import get_optional_current_user
from app.database.repository.user import User

# status da inscrição -> cor do badge (cores padrão do Quasar)
STATUS_COR = {
    "pendente": "warning",
    "confirmada": "positive",
    "cancelada": "negative",
}
STATUS_ROTULO = {
    "pendente": "Pendente",
    "confirmada": "Confirmada",
    "cancelada": "Cancelada",
}


def formatar_moeda(valor: float) -> str:
    """Formata um valor em reais no padrão brasileiro (R$ 1.234,56)."""
    texto = f"{valor:,.2f}"  # 1,234.56
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def status_badge(status: str) -> ui.badge:
    """Badge colorido com o status da inscrição."""
    return ui.badge(STATUS_ROTULO.get(status, status)).props(
        f"color={STATUS_COR.get(status, 'grey')}"
    )


def meia_badge() -> ui.badge:
    """Badge indicando que a inscrição foi feita pela meia-entrada."""
    return ui.badge("Meia-entrada").props("color=blue outline")


def upload_comprovante(
    on_upload: Callable[[events.UploadEventArguments], None],
) -> ui.upload:
    """
    Upload do comprovante (somente PDF) usado nos dialogs de inscrição.

    Retorna ``(upload, arquivos, nome_arquivo)``:

    - ``arquivos`` guarda no máximo **um** arquivo ``(nome, bytes)``: ao
      selecionar um novo arquivo, o anterior é substituído;
    - ``nome_arquivo`` exibe o nome do arquivo selecionado (a lista do
      uploader é limpa após o upload, para liberar a seleção de um novo
      arquivo — por isso o nome fica nesse label);
    - arquivos que não sejam PDF são rejeitados pelo filtro ``accept`` do
      uploader e o ``erro`` é preenchido (a validação definitiva também
      acontece no banco, via ``eh_pdf``).
    """
    nome_arquivo = ui.label().classes("text-body2 text-grey-8")
    nome_arquivo.visible = False

    upload = (
        ui.upload(auto_upload=True, max_files=1)
        .props("accept=.pdf")
        .classes("w-full q-mb-md")
    )

    upload = upload.on_upload(on_upload)

    return upload.on_rejected(lambda: ui.notify("arquivo deve ser um PDF válido"))


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

    As páginas que o usam podem ser públicas: o menu mostra "Minhas
    inscrições" e "Sair" quando a requisição traz um cookie de sessão
    válido, e "Entrar" caso contrário.
    """
    user: User | None = get_optional_current_user(request)
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

            if user is not None:
                with ui.menu_item(
                    "Minhas inscrições", on_click=lambda: ui.navigate.to("/user/events")
                ):
                    with ui.item_section().props("avatar"):
                        _ = ui.icon("assignment")
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
