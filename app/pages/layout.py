"""
Elementos compartilhados entre as páginas: o decorator ``pagina`` (registra
cada rota e renderiza o cabeçalho único da aplicação), badges, formatação
de moeda e de datas, cartões de evento, linhas de ícone+texto, tela de
"não encontrado", dialog de confirmação, upload de comprovante e botão de
voltar ao topo.
"""

import functools
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime
from typing import Any
from nicegui import app, events, ui

from app.database.repository.activity import PreviaAtividade
from app.database.repository.event import Evento
from app.database.repository.user import Usuario

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


def data_hora(quando: datetime) -> str:
    """Formata um datetime no padrão brasileiro (dia/mês/ano às HH:MM)."""
    return quando.strftime("%d/%m/%Y às %H:%M")


def periodo(evento: Evento) -> str:
    """Data do evento; eventos de vários dias mostram o intervalo."""
    inicio = evento.data_hora_inicio.date()
    fim = evento.data_hora_fim.date()
    if inicio == fim:
        return inicio.strftime("%d/%m/%Y")
    return f"{inicio:%d/%m/%Y} – {fim:%d/%m/%Y}"


def horario_atividade(atividade: PreviaAtividade) -> str:
    """Intervalo completo de uma atividade ("início – fim")."""
    return f"{data_hora(atividade.data_hora_inicio)} – {data_hora(atividade.data_hora_fim)}"


@contextmanager
def item_icone(icone: str, tamanho: str = "18px") -> Iterator[None]:
    """Linha "ícone + conteúdo": o corpo do ``with`` entra ao lado do ícone."""
    with ui.row().classes("items-center gap-1"):
        _ = ui.icon(icone, size=tamanho)
        yield


def linha_de_icones(itens: Sequence[tuple[str, str]]) -> None:
    """Sequência de pares "ícone + texto" em uma linha (cartões de listagem)."""
    with ui.row().classes("items-center gap-x-6 gap-y-1 text-grey-8"):
        for icone, texto in itens:
            with item_icone(icone):
                _ = ui.label(texto).classes("text-body2")


def preco(evento: Evento) -> None:
    """Preço do evento com ícone; "Gratuito" quando o valor é zero."""
    with ui.row().classes("items-center gap-1"):
        _ = ui.icon("attach_money", size="16px")
        if evento.valor > 0:
            _ = ui.label(formatar_moeda(evento.valor)).classes("text-body2")
        else:
            _ = ui.label("Gratuito").classes("text-body2 text-positive")


def corpo_evento(evento: Evento) -> None:
    """Corpo do cartão de evento: imagem (ou espaço reservado), nome, data e preço."""
    if evento.banner_thumbnail:
        _ = ui.image(evento.banner_thumbnail).classes("w-full aspect-video")
    else:
        # evento sem imagem: mantém a mesma proporção para alinhar o grid
        with ui.element("div").classes(
            "w-full aspect-video flex items-center justify-center bg-grey-4"
        ):
            _ = ui.icon("event", size="48px").classes("text-grey-7")
    with ui.card_section().classes("w-full"):
        _ = ui.label(evento.nome).classes("text-subtitle1 text-weight-medium")
        with ui.row().classes("items-center gap-x-4 gap-y-1 text-grey-7"):
            with ui.row().classes("items-center gap-1"):
                _ = ui.icon("calendar_today", size="16px")
                _ = ui.label(periodo(evento)).classes("text-body2")
                if (evento.inscritas or 0) >= evento.vagas:
                    _ = ui.label("Lotado").classes("text-body2")

            preco(evento)


def cartao_evento(evento: Evento) -> None:
    """Cartão de evento com link para os detalhes (página inicial)."""
    with (
        ui.link(target=f"/event/{evento.id}").classes("no-underline text-inherit"),
        ui.card().tight().classes("w-full h-full cursor-pointer"),
    ):
        corpo_evento(evento)


def nao_encontrado(
    icone: str, titulo: str, destino: str | None = None, texto_link: str | None = None
) -> None:
    """
    Tela de "não encontrado" das rotas parametrizadas: ícone, título e, se
    informado, um link de volta (``destino``/``texto_link``).
    """
    with ui.column().classes("w-full items-center q-mt-xl"):
        _ = ui.icon(icone, size="64px").classes("text-grey-6")
        _ = ui.label(titulo).classes("text-h6")
        if destino is not None:
            _ = ui.link(texto_link or "Voltar", destino)


def dialogo_confirmacao(
    titulo: str,
    mensagem: str,
    rotulo_acao: str,
    cor: str,
    ao_confirmar: Callable[[Callable[[], None]], None],
    rotulo_cancelar: str = "Voltar",
    marca: str | None = None,
) -> None:
    """
    Dialog de confirmação para ações destrutivas ou irreversíveis.

    ``ao_confirmar`` recebe ``fechar`` e decide quando fechar o dialog: erros
    da ação notificam e mantêm o dialog aberto; sucesso fecha (ou navega)
    conforme o chamador. ``marca`` (opcional) vira um ``.mark`` no dialog,
    para seleção em testes de interface.
    """
    dialogo = ui.dialog()
    if marca is not None:
        _ = dialogo.mark(marca)
    with dialogo, ui.card().classes("w-full").style("max-width: 420px"):
        _ = ui.label(titulo).classes("text-h6")
        _ = ui.label(mensagem).classes("text-body2 text-grey-7")
        with ui.row().classes("w-full q-mt-md"):
            _ = ui.space()
            _ = ui.button(rotulo_cancelar, on_click=dialogo.close).props("flat")

            def confirmar() -> None:
                ao_confirmar(dialogo.close)

            _ = ui.button(rotulo_acao, on_click=confirmar).props(f"color={cor}")
    dialogo.open()


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

    Retorna o controle de upload configurado:

    - ao selecionar um novo arquivo, o anterior é substituído
      (``max_files=1`` e a lista é limpa após o upload, pelo chamador);
    - o nome do arquivo selecionado fica por conta do chamador (o uploader
      limpa a lista após o upload, então o nome precisa ser guardado à
      parte);
    - arquivos que não sejam PDF são rejeitados pelo filtro ``accept`` do
      uploader e o ``erro`` é preenchido (a validação definitiva também
      acontece no banco, via ``eh_pdf``).
    """
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


def pagina(
    caminho: str, *, com_cabecalho: bool = True, **kwargs_ui_page: Any
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator que registra uma página da aplicação (uma volta sobre ``@ui.page``).

    Além de criar a rota, renderiza o cabeçalho ``cabecalho`` **uma única vez
    por página** em um ponto central: os construtores de página apenas montam
    o conteúdo e nunca chamam o componente por si mesmos. O usuário exibido
    no menu vem do parâmetro ``usuario`` declarado na função da página, com a
    dependência FastAPI que cada página já resolve (``obter_usuario``,
    ``obter_usuario_opcional``); páginas sem esse parâmetro ganham o
    cabeçalho de visitante (menu "Entrar"). ``com_cabecalho=False`` exclui a
    única página dedicada que não o usa (login, tela cheia). Os demais
    argumentos (``dependencies``, ``title``, ...) são repassados ao
    ``@ui.page``.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @ui.page(caminho, **kwargs_ui_page)
        @functools.wraps(func)
        def construir_pagina(*args: Any, **argumentos: Any) -> Any:
            if com_cabecalho:
                cabecalho(argumentos.get("usuario"))
            return func(*args, **argumentos)

        return construir_pagina

    return decorator


def cabecalho(usuario: Usuario | None) -> None:
    """
    Cabeçalho com o título (link para a página inicial) e o menu do usuário.

    Não é chamado pelas páginas: o decorator ``pagina`` o renderiza uma única
    vez para cada rota registrada da aplicação. O menu mostra "Minhas
    inscrições" e "Sair" quando ``usuario`` é um usuário autenticado (páginas
    privadas o declaram com ``Annotated[Usuario, Depends(obter_usuario)]``),
    e "Entrar" caso contrário (páginas públicas usam ``Usuario | None`` com
    ``Depends(obter_usuario_opcional)``).

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

            if usuario is not None:
                with (
                    ui.menu_item(),
                    ui.item_section().props("avatar"),
                ):
                    _ = ui.label(usuario.nome)

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


def voltar_ao_topo() -> None:
    with ui.page_scroller(position="bottom-right", x_offset=20, y_offset=20):
        _ = ui.button("Voltar ao topo")
