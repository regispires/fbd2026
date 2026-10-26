"""
Páginas de atividades de um evento.

- ``/event/{event_id}/activities``: listagem das atividades do evento, com
  o dialog de criação (administrador).
- ``/event/{event_id}/activities/{activity_id}``: detalhes da atividade —
  administradores editam os campos, gerenciam ministrantes e registram
  presenças; a lista de quem pode receber presença só aparece para eles.

Página pública (como a de eventos): visitantes veem os dados da atividade
e dos ministrantes, sem CPF/e-mail; a seção de presenças não é renderizada
para outros papéis.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated

from fastapi import Depends
from nicegui import ui

from app.auth import get_optional_current_user
from app.database.repository.activity import (
    Activity,
    ActivityList,
    ActivityPreview,
    Lecturer,
    User,
    delete_activity,
    get_activity,
    get_lecturers,
)
from app.database.repository.event import Event, EventNotFound, get_event
from app.database.repository.inscription_list import (
    add_attendance,
    get_activity_attendance,
    get_participants,
    remove_attendance,
)
from app.database.repository.user import get_users
from app.exceptions import (
    ActivityHasDependencies,
    ActivityNotFound,
    ActivityWithoutLecturer,
    AttendanceNotFound,
    DuplicateAttendance,
    DuplicateLecturer,
    EventInscriptionNotConfirmed,
    InvalidActivitySchedule,
    NoMoreVacancy,
)
from app.pages.event_form import (
    campo_com_erro,
    coletar_dados_atividade,
    conectar_atividade_ao_evento,
    linha_atividade,
    obrigatorio,
    seletor_ministrantes,
    valores_atividade,
    vazio_para_none,
)
from app.pages.layout import page, scroll_to_top


def _data_hora(dt: datetime) -> str:
    return dt.strftime("%d/%m/%Y às %H:%M")


def _horario_atividade(activity: ActivityPreview) -> str:
    inicio, fim = activity.data_hora_inicio, activity.data_hora_fim
    return f"{_data_hora(inicio)} – {_data_hora(fim)}"


def _evento_nao_encontrado() -> None:
    with ui.column().classes("w-full items-center q-mt-xl"):
        _ = ui.icon("event_busy", size="64px").classes("text-grey-6")
        _ = ui.label("Evento não encontrado").classes("text-h6")
        _ = ui.link("Voltar para a lista de eventos", "/")


def _atividade_nao_encontrada(event_id: int) -> None:
    with ui.column().classes("w-full items-center q-mt-xl"):
        _ = ui.icon("event_note", size="64px").classes("text-grey-6")
        _ = ui.label("Atividade não encontrada").classes("text-h6")
        _ = ui.link("Voltar para o evento", f"/event/{event_id}")


# --- Listagem e criação -----------------------------------------------------


def _cartao_lista(event: Event, atividade: ActivityPreview) -> None:
    """Cartão de atividade na listagem; o nome é o link para os detalhes."""
    with (
        ui.card().mark(f"atividade-{atividade.id}").classes("w-full"),
        ui.column().classes("w-full gap-2"),
    ):
        _ = ui.link(
            atividade.nome,
            f"/event/{event.id}/activities/{atividade.id}",
        ).classes("text-h6 text-weight-medium no-underline text-inherit")
        with ui.row().classes("items-center gap-x-6 gap-y-1 text-grey-8"):
            for icon, texto in (
                ("schedule", _horario_atividade(atividade)),
                ("meeting_room", atividade.sala),
                ("event_seat", f"{atividade.vagas} vagas"),
            ):
                with ui.row().classes("items-center gap-1"):
                    _ = ui.icon(icon, size="18px")
                    _ = ui.label(texto).classes("text-body2")


def _dialogo_criar_atividade(event: Event, atividades: ActivityList) -> None:
    """
    Dialog de criação de atividade (administrador).

    Coleta os campos da atividade e pelo menos um ministrante (regra de
    negócio), com o horário validado inline contra o intervalo do evento;
    atividade e ministrantes são criados na mesma transação.
    """
    usuarios = get_users()

    with (
        ui.dialog().mark("dialog-criar-atividade") as dialogo,
        ui.card().classes("w-full").style("max-width: 700px"),
    ):
        _ = ui.label(f"Nova atividade — {event.nome}").classes("text-h6")
        form = linha_atividade()
        conectar_atividade_ao_evento(form, event)

        _ = ui.label("Ministrantes").classes("text-subtitle1 q-mt-md")
        seletor = seletor_ministrantes(usuarios)

        def criar() -> None:
            valores = coletar_dados_atividade(form, event)
            if valores is None:
                return
            ministrantes = seletor.coletar()
            if ministrantes is None:
                return
            try:
                atividade = atividades.add(
                    event_id=event.id,
                    nome=valores.nome,
                    descricao=valores.descricao,
                    sala=valores.sala,
                    vagas=valores.vagas,
                    data_hora_inicio=valores.data_hora_inicio,
                    data_hora_fim=valores.data_hora_fim,
                    lecturers=ministrantes,
                )
            except InvalidActivitySchedule:
                ui.notify(
                    "O horário da atividade precisa estar contido no do evento.",
                    type="negative",
                )
                return
            except ActivityWithoutLecturer:
                ui.notify(
                    "A atividade precisa de pelo menos um ministrante.",
                    type="negative",
                )
                return
            except DuplicateLecturer:
                ui.notify(
                    "Um usuário não pode ministrar a mesma atividade duas vezes.",
                    type="negative",
                )
                return
            dialogo.close()
            ui.notify("Atividade criada.", type="positive")
            ui.navigate.to(f"/event/{event.id}/activities/{atividade.id}")

        with ui.row().classes("w-full q-mt-md"):
            _ = ui.space()
            _ = ui.button("Cancelar", on_click=dialogo.close).props("flat")
            _ = ui.button("Criar", on_click=criar).props("color=primary")

    dialogo.open()


@page("/event/{event_id}/activities")
def activities_page(
    event_id: int,
    user: Annotated[User | None, Depends(get_optional_current_user)],
):
    try:
        event = get_event(event_id)
    except EventNotFound:
        _evento_nao_encontrado()
        return

    eh_admin = user is not None and user.papel == "administrador"

    with ui.column().classes("w-full gap-4").style("max-width: 1000px; margin: 0 auto"):
        with ui.row().classes("w-full items-center"):
            _ = ui.link(f"← {event.nome}", f"/event/{event.id}").classes(
                "text-primary"
            )
            if eh_admin:
                _ = ui.space()
                _ = ui.button(
                    "Criar atividade",
                    icon="add",
                    on_click=lambda: _dialogo_criar_atividade(event, atividades),
                ).props("color=primary")

        _ = ui.label("Atividades").classes("text-h5")

        @ui.refreshable
        def lista() -> None:
            if not atividades.items:
                _ = ui.label("Nenhuma atividade cadastrada.").classes("text-grey-7")
                return
            for atividade in atividades.items:
                _cartao_lista(event, atividade)

        atividades = ActivityList(items=[], on_change=lista.refresh)
        lista()
        atividades.set_event(event_id)
        atividades.reload()

    scroll_to_top()


# --- Detalhes: edição e exclusão --------------------------------------------


def _dialogo_editar_atividade(event: Event, atividade: Activity) -> None:
    """
    Dialog de edição da atividade, pré-preenchido.

    O horário é validado inline contra o intervalo do evento (e novamente
    no repositório, na mesma transação da escrita, contra o horário atual
    do evento).
    """
    with (
        ui.dialog().mark("dialog-editar-atividade") as dialogo,
        ui.card().classes("w-full").style("max-width: 700px"),
    ):
        _ = ui.label(f"Editar {atividade.nome}").classes("text-h6")
        form = linha_atividade(valores_atividade(atividade))
        conectar_atividade_ao_evento(form, event)

        def salvar() -> None:
            # validações de servidor: erros aparecem nos próprios campos
            valores = coletar_dados_atividade(form, event)
            if valores is None:
                return
            try:
                atividade.update(
                    nome=valores.nome,
                    descricao=valores.descricao,
                    sala=valores.sala,
                    vagas=valores.vagas,
                    data_hora_inicio=valores.data_hora_inicio,
                    data_hora_fim=valores.data_hora_fim,
                )
            except InvalidActivitySchedule:
                ui.notify(
                    "O horário da atividade precisa estar contido no do evento.",
                    type="negative",
                )
                return
            dialogo.close()
            ui.notify("Atividade atualizada.", type="positive")
            ui.navigate.to(f"/event/{event.id}/activities/{atividade.id}")

        with ui.row().classes("w-full q-mt-md"):
            _ = ui.space()
            _ = ui.button("Cancelar", on_click=dialogo.close).props("flat")
            _ = ui.button("Salvar", on_click=salvar).props("color=primary")

    dialogo.open()


def _confirmar_exclusao(event: Event, atividade: Activity) -> None:
    """
    Dialog de confirmação da exclusão da atividade.

    A exclusão é bloqueada quando a atividade já recebeu presenças (regra
    de negócio); sem presenças, os vínculos de ministrantes são excluídos
    junto.
    """
    with (
        ui.dialog().mark("dialog-excluir-atividade") as dialogo,
        ui.card().classes("w-full").style("max-width: 420px"),
    ):
        _ = ui.label("Excluir esta atividade?").classes("text-h6")
        _ = ui.label(
            "Os vínculos de ministrantes também serão excluídos. "
            "Esta ação não pode ser desfeita."
        ).classes("text-body2 text-grey-7")

        def confirmar() -> None:
            try:
                removida = delete_activity(atividade.id)
            except ActivityHasDependencies:
                ui.notify(
                    "Esta atividade já possui presenças registradas e não pode "
                    "ser excluída.",
                    type="negative",
                )
                dialogo.close()
                return
            except ActivityNotFound:
                ui.notify("Atividade não encontrada.", type="warning")
                dialogo.close()
                return
            if not removida:
                ui.notify("Atividade não encontrada.", type="warning")
                return
            dialogo.close()
            ui.notify("Atividade excluída.", type="positive")
            ui.navigate.to(f"/event/{event.id}/activities")

        with ui.row().classes("w-full q-mt-md"):
            _ = ui.space()
            _ = ui.button("Voltar", on_click=dialogo.close).props("flat")
            _ = ui.button("Excluir", on_click=confirmar).props("color=negative")

    dialogo.open()


# --- Ministrantes -----------------------------------------------------------


def _cartao_ministrante(
    atividade: Activity,
    lecturer: Lecturer,
    eh_admin: bool,
    atualizar: Callable[[], None],
) -> None:
    """Card de ministrante com as ações administrativas (editar/remover)."""
    with (
        ui.card().mark(f"ministrante-{lecturer.user.id}").classes("w-full"),
        ui.row().classes("w-full items-start gap-3"),
    ):
        _ = ui.icon("person", size="24px").classes("text-primary")
        with ui.column().classes("gap-0 flex-grow"):
            with ui.row().classes("items-center gap-2"):
                _ = ui.label(lecturer.user.nome).classes("text-weight-medium")
                _ = ui.label(lecturer.instituicao).classes("text-grey-7")
                if lecturer.link_lattes:
                    _ = ui.link("Lattes", lecturer.link_lattes, new_tab=True).props(
                        "flat dense no-caps color=primary"
                    )
            if lecturer.mini_bio:
                _ = ui.label(lecturer.mini_bio).classes("text-body2 text-grey-8")
        if eh_admin:
            _ = ui.button(
                "Editar dados",
                icon="edit",
                on_click=lambda: _dialogo_editar_ministrante(
                    atividade, lecturer, atualizar
                ),
            ).props("flat dense no-caps")
            _ = ui.button(
                "Remover",
                icon="delete",
                on_click=lambda: _confirmar_remocao_ministrante(
                    atividade, lecturer, atualizar
                ),
            ).props("flat dense no-caps color=negative")


def _dialogo_editar_ministrante(
    atividade: Activity, lecturer: Lecturer, atualizar: Callable[[], None]
) -> None:
    """
    Edita os dados do vínculo de um ministrante (instituição obrigatória,
    mini-bio e Lattes opcionais). O usuário em si não é alterado.
    """
    with (
        ui.dialog().mark("dialog-editar-ministrante") as dialogo,
        ui.card().classes("w-full").style("max-width: 500px"),
    ):
        _ = ui.label(f"Editar ministrante — {lecturer.user.nome}").classes("text-h6")
        instituicao = ui.input(
            "Instituição *",
            value=lecturer.instituicao,
            validation={"Informe a instituição.": obrigatorio},
        ).classes("w-full")
        mini_bio = ui.textarea("Mini-bio", value=lecturer.mini_bio or "").classes(
            "w-full"
        )
        link_lattes = ui.input(
            "Link do Lattes", value=lecturer.link_lattes or ""
        ).classes("w-full")

        def salvar() -> None:
            instituicao.validate()
            if campo_com_erro(instituicao):
                return
            atividade.update_lecturer(
                user_id=lecturer.id_usuario,
                mini_bio=vazio_para_none(mini_bio.value),
                instituicao=(instituicao.value or "").strip(),
                link_lattes=vazio_para_none(link_lattes.value),
            )
            dialogo.close()
            ui.notify("Dados do ministrante atualizados.", type="positive")
            atualizar()

        with ui.row().classes("w-full q-mt-md"):
            _ = ui.space()
            _ = ui.button("Cancelar", on_click=dialogo.close).props("flat")
            _ = ui.button("Salvar", on_click=salvar).props("color=primary")

    dialogo.open()


def _confirmar_remocao_ministrante(
    atividade: Activity, lecturer: Lecturer, atualizar: Callable[[], None]
) -> None:
    """
    Dialog de confirmação antes de remover um ministrante (ação
    destrutiva; a regra impede a atividade de ficar sem ministrantes).
    """
    with (
        ui.dialog().mark("dialog-remover-ministrante") as dialogo,
        ui.card().classes("w-full").style("max-width: 420px"),
    ):
        _ = ui.label("Remover ministrante?").classes("text-h6")
        _ = ui.label(
            f"{lecturer.user.nome} deixará de ministrar esta atividade. "
            "A atividade precisa de pelo menos um ministrante."
        ).classes("text-body2 text-grey-7")

        def confirmar() -> None:
            try:
                removido = atividade.remove_lecturer(lecturer.id_usuario)
            except ActivityWithoutLecturer:
                ui.notify(
                    "A atividade precisa de pelo menos um ministrante.",
                    type="negative",
                )
                return
            if not removido:
                ui.notify("Ministrante não encontrado.", type="warning")
                atualizar()
                dialogo.close()
                return
            dialogo.close()
            ui.notify("Ministrante removido.", type="positive")
            atualizar()

        with ui.row().classes("w-full q-mt-md"):
            _ = ui.space()
            _ = ui.button("Voltar", on_click=dialogo.close).props("flat")
            _ = ui.button("Remover", on_click=confirmar).props("color=negative")

    dialogo.open()


def _dialogo_adicionar_ministrantes(
    atividade: Activity, atualizar: Callable[[], None]
) -> None:
    """
    Dialog de adição de ministrantes: multiselect com os usuários que
    ainda não ministram a atividade e, para cada selecionado, os campos do
    vínculo.
    """
    existentes = {m.id_usuario for m in get_lecturers(atividade.id_evento, atividade.id)}
    candidatos = [u for u in get_users() if u.id not in existentes]
    if not candidatos:
        ui.notify("Todos os usuários já ministram esta atividade.")
        return

    with (
        ui.dialog().mark("dialog-adicionar-ministrantes") as dialogo,
        ui.card().classes("w-full").style("max-width: 700px"),
    ):
        _ = ui.label("Adicionar ministrantes").classes("text-h6")
        seletor = seletor_ministrantes(candidatos)

        def adicionar() -> None:
            ministrantes = seletor.coletar()
            if ministrantes is None:
                return
            try:
                atividade.add_lecturers(ministrantes)
            except DuplicateLecturer:
                ui.notify(
                    "Um usuário não pode ministrar a mesma atividade duas vezes.",
                    type="negative",
                )
                dialogo.close()
                atualizar()
                return
            dialogo.close()
            ui.notify("Ministrantes adicionados.", type="positive")
            atualizar()

        with ui.row().classes("w-full q-mt-md"):
            _ = ui.space()
            _ = ui.button("Cancelar", on_click=dialogo.close).props("flat")
            _ = ui.button("Adicionar", on_click=adicionar).props("color=primary")

    dialogo.open()


# --- Presenças --------------------------------------------------------------


def _confirmar_remocao_presenca(
    atividade: Activity, participante: User, atualizar: Callable[[], None]
) -> None:
    """Dialog de confirmação antes de desfazer a presença de um participante."""
    with (
        ui.dialog().mark("dialog-remover-presenca") as dialogo,
        ui.card().classes("w-full").style("max-width: 420px"),
    ):
        _ = ui.label("Remover presença?").classes("text-h6")
        _ = ui.label(
            f"A presença de {participante.nome} nesta atividade será desfeita. "
            "Esta ação não pode ser desfeita."
        ).classes("text-body2 text-grey-7")

        def confirmar() -> None:
            try:
                remove_attendance(participante.id, atividade.id_evento, atividade.id)
            except AttendanceNotFound:
                ui.notify(
                    "Presença não encontrada (já removida em outra aba?).",
                    type="warning",
                )
            else:
                ui.notify("Presença removida.", type="positive")
            dialogo.close()
            atualizar()

        with ui.row().classes("w-full q-mt-md"):
            _ = ui.space()
            _ = ui.button("Voltar", on_click=dialogo.close).props("flat")
            _ = ui.button("Remover", on_click=confirmar).props("color=negative")

    dialogo.open()


def _dialogo_registrar_presenca(
    atividade: Activity, atualizar: Callable[[], None]
) -> None:
    """
    Dialog de registro de presença (administrador): lista somente os
    inscritos **confirmados** no evento que ainda não têm presença — o
    ``add_attendance`` exige inscrição confirmada, dentro das vagas da
    atividade e sem presença duplicada.
    """
    presentes_ids = {
        u.id for u in get_activity_attendance(atividade.id_evento, atividade.id)
    }
    candidatos = [
        u for u in get_participants(atividade.id_evento) if u.id not in presentes_ids
    ]
    if not candidatos:
        ui.notify("Nenhum inscrito confirmado está sem presença.")
        return

    with (
        ui.dialog().mark("dialog-registrar-presenca") as dialogo,
        ui.card().classes("w-full").style("max-width: 500px"),
    ):
        _ = ui.label(f"Registrar presença — {atividade.nome}").classes("text-h6")
        _ = ui.label(
            "Somente inscritos confirmados no evento podem receber presença."
        ).classes("text-caption text-grey-7")
        select = ui.select(
            {u.id: f"{u.nome} — {u.email}" for u in candidatos},
            multiple=True,
            label="Participantes *",
        ).classes("w-full")
        erro = ui.label("Selecione pelo menos um participante.").classes(
            "text-negative text-caption"
        )
        erro.visible = False

        def registrar() -> None:
            selecionados = select.value or []
            if not selecionados:
                erro.visible = True
                return
            adicionadas = 0
            for user_id in selecionados:
                try:
                    _ = add_attendance(user_id, atividade.id_evento, atividade.id)
                except DuplicateAttendance:
                    continue  # presença já registrada (página desatualizada)
                except NoMoreVacancy:
                    ui.notify(
                        "As vagas de presença desta atividade acabaram.",
                        type="warning",
                    )
                    break
                except EventInscriptionNotConfirmed:
                    ui.notify(
                        "Participante sem inscrição confirmada no evento.",
                        type="warning",
                    )
                    continue
                adicionadas += 1
            if adicionadas:
                ui.notify(
                    f"Presença registrada para {adicionadas} participante(s).",
                    type="positive",
                )
            dialogo.close()
            atualizar()

        with ui.row().classes("w-full q-mt-md"):
            _ = ui.space()
            _ = ui.button("Cancelar", on_click=dialogo.close).props("flat")
            _ = ui.button("Registrar", on_click=registrar).props("color=primary")

    dialogo.open()


# --- Detalhes da atividade --------------------------------------------------


@page("/event/{event_id}/activities/{activity_id}")
def activity_page(
    event_id: int,
    activity_id: int,
    user: Annotated[User | None, Depends(get_optional_current_user)],
):
    try:
        event = get_event(event_id)
    except EventNotFound:
        _evento_nao_encontrado()
        return

    try:
        atividade = get_activity(activity_id, event_id)
    except ActivityNotFound:
        _atividade_nao_encontrada(event_id)
        return

    eh_admin = user is not None and user.papel == "administrador"

    @ui.refreshable
    def secao_ministrantes() -> None:
        """Ministrantes da atividade; as ações administrativas aparecem junto."""
        ministrantes = get_lecturers(event_id, atividade.id)
        _ = ui.label("Ministrantes").classes("text-h5")
        if not ministrantes:
            _ = ui.label("Nenhum ministrante cadastrado.").classes("text-grey-7")
        for lecturer in ministrantes:
            _cartao_ministrante(
                atividade, lecturer, eh_admin, secao_ministrantes.refresh
            )
        if eh_admin:
            _ = ui.button(
                "Adicionar ministrantes",
                icon="add",
                on_click=lambda: _dialogo_adicionar_ministrantes(
                    atividade, secao_ministrantes.refresh
                ),
            ).props("flat no-caps")

    @ui.refreshable
    def secao_presenca() -> None:
        """
        Presenças da atividade, somente para administradores: a lista de
        quem pode receber presença nunca aparece para outros papéis (regra
        de negócio).
        """
        presentes = get_activity_attendance(event_id, atividade.id)
        ids_presentes = {u.id for u in presentes}
        candidatos = [
            u for u in get_participants(event_id) if u.id not in ids_presentes
        ]

        _ = ui.label("Presenças").classes("text-h5")
        _ = ui.label(
            f"{len(presentes)} de {atividade.vagas} vaga(s) de presença preenchidas."
        ).classes("text-caption text-grey-7")

        if presentes:
            for participante in presentes:
                with (
                    ui.card()
                    .mark(f"presenca-{participante.id}")
                    .classes("w-full"),
                    ui.row().classes("w-full items-center gap-3"),
                ):
                    _ = ui.icon("check_circle", size="24px").classes("text-positive")
                    with ui.column().classes("gap-0 flex-grow"):
                        _ = ui.label(participante.nome).classes("text-subtitle1")
                    _ = ui.button(
                        "Remover presença",
                        icon="person_remove",
                        on_click=lambda u=participante: _confirmar_remocao_presenca(
                            atividade, u, secao_presenca.refresh
                        ),
                    ).props("flat dense no-caps color=negative")
        else:
            _ = ui.label("Nenhuma presença registrada.").classes("text-grey-7")

        with ui.row().classes("w-full items-center"):
            if candidatos:
                _ = ui.label(
                    f"{len(candidatos)} inscrito(s) confirmado(s) ainda sem presença."
                ).classes("text-caption text-grey-7")
                _ = ui.space()
                _ = ui.button(
                    "Registrar presença",
                    icon="how_to_reg",
                    on_click=lambda: _dialogo_registrar_presenca(
                        atividade, secao_presenca.refresh
                    ),
                ).props("color=primary")
            else:
                _ = ui.label(
                    "Nenhum inscrito confirmado sem presença: aprove as inscrições "
                    "pendentes do evento para registrar presença."
                ).classes("text-caption text-grey-7")

    with ui.column().classes("w-full gap-4").style("max-width: 1000px; margin: 0 auto"):
        with ui.row().classes("w-full items-center gap-1"):
            _ = ui.link(f"← {event.nome}", f"/event/{event.id}").classes(
                "text-primary"
            )
            _ = ui.link("Atividades", f"/event/{event.id}/activities").props(
                "flat dense no-caps color=primary"
            )
            if eh_admin:
                _ = ui.space()
                _ = ui.button(
                    "Editar",
                    icon="edit",
                    on_click=lambda: _dialogo_editar_atividade(event, atividade),
                ).mark("botao-editar-atividade").props("flat dense no-caps")
                _ = ui.button(
                    "Excluir",
                    icon="delete",
                    on_click=lambda: _confirmar_exclusao(event, atividade),
                ).props("flat dense no-caps color=negative")

        _ = ui.label(atividade.nome).classes("text-h4")

        with ui.card().classes("w-full"), ui.column().classes("w-full gap-2"):
            with ui.row().classes("items-center gap-x-6 gap-y-1 text-grey-8"):
                for icon, texto in (
                    ("schedule", _horario_atividade(atividade)),
                    ("meeting_room", atividade.sala),
                    ("event_seat", f"{atividade.vagas} vagas"),
                ):
                    with ui.row().classes("items-center gap-1"):
                        _ = ui.icon(icon, size="18px")
                        _ = ui.label(texto).classes("text-body2")
            if atividade.descricao:
                _ = ui.label(atividade.descricao).classes("text-body1")

        secao_ministrantes()

        if eh_admin:
            secao_presenca()

    scroll_to_top()
