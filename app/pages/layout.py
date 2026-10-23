"""
Elementos compartilhados entre as páginas: o decorator ``page`` (registra
cada rota e renderiza o cabeçalho único da aplicação), badges, formatação de
moeda, upload de comprovante e botão de voltar ao topo.
"""

import functools
from collections.abc import Callable
from typing import Any

from nicegui import app, events, ui

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

# chave da preferência de tema no ``app.storage.general``: escolha global da
# aplicação (não por navegador), persistida em ``.nicegui/storage-general.json``
CHAVE_TEMA = "tema_escuro"


def _salvar_tema(evento: events.ValueChangeEventArguments[bool | None]) -> None:
    """Guarda a preferência de tema da aplicação no storage compartilhado."""
    app.storage.user[CHAVE_TEMA] = evento.value


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


def page(
    path: str, *, with_header: bool = True, **ui_page_kwargs: Any
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator que registra uma página da aplicação (uma volta sobre ``@ui.page``).

    Além de criar a rota, renderiza o cabeçalho ``header`` **uma única vez por
    página** em um ponto central: os construtores de página apenas montam o
    conteúdo e nunca chamam o componente por si mesmos. O usuário exibido no
    menu vem do parâmetro ``user`` declarado na função da página, com a
    dependência FastAPI que cada página já resolve (``get_current_user``,
    ``get_optional_current_user``); páginas sem esse parâmetro ganham o
    cabeçalho de visitante (menu "Entrar"). ``with_header=False`` exclui a
    única página dedicada que não o usa (login, tela cheia). Os demais
    argumentos (``dependencies``, ``title``, ...) são repassados ao ``@ui.page``.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @ui.page(path, **ui_page_kwargs)
        @functools.wraps(func)
        def build_page(*args: Any, **arguments: Any) -> Any:
            if with_header:
                header(arguments.get("user"))
            return func(*args, **arguments)

        return build_page

    return decorator


def header(user: User | None) -> None:
    """
    Cabeçalho com o título (link para a página inicial) e o menu do usuário.

    Não é chamado pelas páginas: o decorator ``page`` o renderiza uma única
    vez para cada rota registrada da aplicação. O menu mostra "Minhas
    inscrições" e "Sair" quando ``user`` é um usuário autenticado (páginas
    privadas o declaram com ``Annotated[User, Depends(get_current_user)]``),
    e "Entrar" caso contrário (páginas públicas usam ``User | None`` com
    ``Depends(get_optional_current_user)``).

    O tema escolhido no switch fica em ``app.storage.general``: preferência
    global persistida da aplicação, revalidada a cada navegação/recarga.
    """
    with ui.header(bordered=True, elevated=True).style(
        "display: flex; align-items: center;"
    ):
        # fora do ``ui.menu``: o conteúdo do menu só renderiza após a
        # primeira abertura, e o elemento precisa existir na página desde o
        # carregamento para aplicar a preferência salva no storage
        dark = ui.dark_mode(
            app.storage.user.get(CHAVE_TEMA, False), on_change=_salvar_tema
        )
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
                    _ = ui.icon("dark_mode")
                _ = ui.switch().bind_value(dark).props("dense color=accent")

            _ = ui.separator()

            if user is not None:
                with (
                    ui.menu_item(),
                    ui.item_section().props("avatar"),
                ):
                    _ = ui.label(user.nome)

                with (
                    ui.menu_item(
                        "Minhas inscrições",
                        on_click=lambda: ui.navigate.to("/user/events"),
                    ),
                    ui.item_section().props("avatar"),
                ):
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
