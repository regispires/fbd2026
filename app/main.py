from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from nicegui import app, ui

from app import (
    api,  # noqa: F401  (rotas de API criadas na importação)
    pages,  # noqa: F401  (rotas das páginas criadas na importação)
)
from app.auth import get_optional_current_user
from app.database.repository.activity import ActivityInput
from app.database.repository.event import Event, EventList, create_event
from app.database.repository.user import User, get_users
from app.database.settings import settings
from app.exceptions import (
    ActivityWithoutLecturer,
    DuplicateEventRegistration,
    DuplicateLecturer,
    InvalidActivitySchedule,
)
from app.pages.event_form import (
    ActivityForm,
    SeletorMinistrantes,
    campos_evento,
    coletar_atividade,
    coletar_valores,
    conectar_atividade,
    conectar_validacao_evento,
    linha_atividade,
    seletor_ministrantes,
)
from app.pages.layout import formatar_moeda, header


def _periodo(event: Event) -> str:
    """Data do evento; eventos de vários dias mostram o intervalo."""
    inicio = event.data_hora_inicio.date()
    fim = event.data_hora_fim.date()
    if inicio == fim:
        return inicio.strftime("%d/%m/%Y")
    return f"{inicio:%d/%m/%Y} – {fim:%d/%m/%Y}"


def _preco(event: Event) -> None:
    with ui.row().classes("items-center gap-1"):
        _ = ui.icon("attach_money", size="16px")
        if event.valor > 0:
            _ = ui.label(formatar_moeda(event.valor)).classes("text-body2")
        else:
            _ = ui.label("Gratuito").classes("text-body2 text-positive")


def _corpo(event: Event) -> None:
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
        with ui.row().classes("items-center gap-x-4 gap-y-1 text-grey-7"):
            with ui.row().classes("items-center gap-1"):
                _ = ui.icon("calendar_today", size="16px")
                _ = ui.label(_periodo(event)).classes("text-body2")
                if (event.inscritas or 0) >= event.vagas:
                    _ = ui.label("Lotado").classes("text-body2")

            _preco(event)


def _event_card(event: Event) -> None:
    with (
        ui.link(target=f"/event/{event.id}").classes("no-underline text-inherit"),
        ui.card().tight().classes("w-full h-full cursor-pointer"),
    ):
        _corpo(event)


def _dialogo_criar_evento(ao_sucesso: Callable[[int], None]) -> None:
    """
    Dialog administrativo de criação de evento.

    O evento precisa ter pelo menos uma atividade (regra de negócio), então
    o dialog também lista as atividades a criar; cada uma precisa estar
    contida no horário do evento e ter ao menos um ministrante. Ao concluir,
    ``ao_sucesso`` recebe o id do evento criado.
    """
    linhas: list[tuple[ui.card, ActivityForm, SeletorMinistrantes]] = []
    revalidadores: list[Callable[[], None]] = []
    usuarios = get_users()

    with ui.dialog() as dialogo, ui.card().classes("w-full").style("max-width: 900px"):
        _ = ui.label("Criar evento").classes("text-h6")
        form = campos_evento()
        # validações de múltiplos campos do evento (datas e lat/lng) exibidas
        # inline, como as validações por campo
        conectar_validacao_evento(form)

        with ui.separator():
            pass

        _ = ui.label("Atividades (pelo menos uma)").classes("text-subtitle1")
        with ui.column().classes("w-full gap-2") as atividades_container:
            pass

        def adicionar_linha() -> None:
            with atividades_container:
                card = ui.card().classes("w-full")
                with card:
                    tema = linha_atividade()
                    _ = ui.label("Ministrantes (pelo menos um)").classes(
                        "text-caption text-grey-7 q-mt-sm"
                    )
                    seletor = seletor_ministrantes(usuarios)
            entrada = (card, tema, seletor)

            def remover() -> None:
                linhas.remove(entrada)
                card.delete()

            with card:
                with ui.row().classes("w-full"):
                    _ = ui.space()
                    _ = ui.button(
                        "Remover atividade", icon="delete", on_click=remover
                    ).props("flat dense no-caps color=negative")

            linhas.append(entrada)
            # validação inline "atividade contida no horário do evento"
            revalidadores.append(conectar_atividade(tema, form))

        adicionar_linha()

        # mudanças no horário do evento reavaliam a contenção de todas as linhas
        for campo in (form.data_inicio, form.hora_inicio, form.data_fim, form.hora_fim):
            campo.on_value_change(
                lambda _: [revalidar() for revalidar in revalidadores]
            )

        _ = ui.button(
            "Adicionar atividade", icon="add", on_click=adicionar_linha
        ).props("flat dense no-caps")

        def criar() -> None:
            # validações de servidor: erros aparecem nos próprios campos
            valores = coletar_valores(form)
            if valores is None:
                return

            if not linhas:
                ui.notify("Adicione pelo menos uma atividade.")
                return

            atividades: list[ActivityInput] = []
            for _, tema, seletor in linhas:
                valores_linha = coletar_atividade(tema, form)
                if valores_linha is None:
                    return  # erro exibido nos campos da linha
                ministrantes = seletor.coletar()
                if ministrantes is None:
                    return  # erro exibido no seletor da linha
                atividades.append(
                    ActivityInput(
                        nome=valores_linha.nome,
                        descricao=valores_linha.descricao,
                        sala=valores_linha.sala,
                        vagas=valores_linha.vagas,
                        data_hora_inicio=valores_linha.data_hora_inicio,
                        data_hora_fim=valores_linha.data_hora_fim,
                        lecturers=ministrantes,
                    )
                )

            try:
                evento = create_event(
                    nome=valores.nome,
                    descricao=valores.descricao,
                    data_hora_inicio=valores.data_hora_inicio,
                    data_hora_fim=valores.data_hora_fim,
                    classificacao_indicativa=valores.classificacao_indicativa,
                    vagas=valores.vagas,
                    valor=valores.valor,
                    latitude=valores.latitude,
                    longitude=valores.longitude,
                    banner=valores.banner,
                    banner_thumbnail=valores.banner_thumbnail,
                    activities=atividades,
                )
            except DuplicateEventRegistration:
                ui.notify("Já existe um evento com esse nome.")
                return
            except InvalidActivitySchedule:
                ui.notify(
                    "O horário de cada atividade precisa estar contido no do evento."
                )
                return
            except ActivityWithoutLecturer:
                ui.notify("Cada atividade precisa de pelo menos um ministrante.")
                return
            except DuplicateLecturer:
                ui.notify("Um usuário não pode ministrar a mesma atividade duas vezes.")
                return
            dialogo.close()
            ao_sucesso(evento.id)

        with ui.row().classes("w-full q-mt-md"):
            _ = ui.space()
            _ = ui.button("Cancelar", on_click=dialogo.close).props("flat")
            _ = ui.button("Criar", on_click=criar).props("color=primary")

    dialogo.open()


@ui.page("/")
def index_page(user: Annotated[User | None, Depends(get_optional_current_user)]):
    header(user)

    eh_admin = user is not None and user.papel == "administrador"

    with ui.row().classes("w-full items-center q-mt-md"):
        _ = ui.label("Eventos").classes("text-h5")
        if eh_admin:
            _ = ui.space()
            _ = ui.button(
                "Criar evento",
                icon="add",
                on_click=lambda: _dialogo_criar_evento(
                    lambda evento_id: ui.navigate.to(f"/event/{evento_id}")
                ),
            ).props("color=primary")

    # 4 eventos por linha em telas largas; em telas menores o grid reduz as
    # colunas para os cards não ficarem espremidos
    @ui.refreshable
    def event_grid() -> None:
        if not events.items:
            _ = ui.label("Nenhum evento cadastrado.").classes("text-grey-7")
            return
        with ui.grid().classes(
            "w-full gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4"
        ):
            for event in events.items:
                _event_card(
                    event,
                )

    events = EventList(items=[], on_change=event_grid.refresh)
    event_grid()
    events.reload()


if __name__ in {
    "__main__",
    "__mp_main__",
}:  # mp_main é necessário por que o nicegui usa multiprocessing
    _ = ui.run(port=8000, storage_secret=settings.STORAGE_SECRET.get_secret_value())
