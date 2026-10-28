"""
Páginas de atividades de um evento.

- ``/event/{evento_id}/activities``: listagem das atividades do evento, com
  o dialog de criação (administrador).
- ``/event/{evento_id}/activities/{atividade_id}``: detalhes da atividade —
  administradores editam os campos, gerenciam ministrantes e registram
  presenças; a lista de quem pode receber presença só aparece para eles.

Página pública (como a de eventos): visitantes veem os dados da atividade
e dos ministrantes, sem CPF/e-mail; a seção de presenças não é renderizada
para outros papéis.
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from nicegui import ui

from app.auth import eh_administrador, obter_usuario_opcional
from app.database.repository.activity import (
    Atividade,
    EntradaAtividade,
    Ministrante,
    PreviaAtividade,
    criar_atividade,
    excluir_atividade,
    listar_atividades,
    listar_ministrantes,
    obter_atividade,
)
from app.database.repository.event import Evento, obter_evento
from app.database.repository.inscription_list import (
    listar_participantes,
    listar_presencas_atividade,
    registrar_presenca,
    remover_presenca,
)
from app.database.repository.user import Usuario, listar_usuarios
from app.exceptions import (
    AtividadeComDependencias,
    AtividadeNaoEncontrada,
    AtividadeSemMinistrante,
    EventoNaoEncontrado,
    EventoSemAtividade,
    HorarioAtividadeInvalido,
    InscricaoNaoConfirmada,
    MinistranteRepetido,
    PresencaNaoEncontrada,
    PresencaRepetida,
    SemVagas,
)
from app.forms.atividade import (
    coletar_atividade,
    conectar_atividade,
    formulario_atividade,
    limites_do_evento,
)
from app.forms.ministrante import seletor_ministrantes
from app.forms.validacao import campo_com_erro, obrigatorio, vazio_para_none
from app.pages.layout import (
    dialogo_confirmacao,
    horario_atividade,
    linha_de_icones,
    nao_encontrado,
    pagina,
    voltar_ao_topo,
)

# --- Listagem e criação -----------------------------------------------------


def _cartao_lista(evento: Evento, atividade: PreviaAtividade) -> None:
    """Cartão de atividade na listagem; o nome é o link para os detalhes."""
    with (
        ui.card().mark(f"atividade-{atividade.id}").classes("w-full"),
        ui.column().classes("w-full gap-2"),
    ):
        _ = ui.link(
            atividade.nome,
            f"/event/{evento.id}/activities/{atividade.id}",
        ).classes("text-h6 text-weight-medium no-underline text-inherit")
        linha_de_icones(
            (
                ("schedule", horario_atividade(atividade)),
                ("meeting_room", atividade.sala),
                ("event_seat", f"{atividade.vagas} vagas"),
            )
        )


def _dialogo_criar_atividade(evento: Evento) -> None:
    """
    Dialog de criação de atividade (administrador).

    Coleta os campos da atividade e pelo menos um ministrante (regra de
    negócio), com o horário validado inline contra o intervalo do evento;
    atividade e ministrantes são criados na mesma transação.
    """
    usuarios = listar_usuarios()

    with (
        ui.dialog().mark("dialog-criar-atividade") as dialogo,
        ui.card().classes("w-full").style("max-width: 900px"),
    ):
        _ = ui.label(f"Nova atividade — {evento.nome}").classes("text-h6")
        with formulario_atividade() as formulario:
            conectar_atividade(formulario, limites_do_evento(evento))

        _ = ui.label("Ministrantes").classes("text-subtitle1 q-mt-md")
        with seletor_ministrantes(usuarios) as seletor:
            pass

        def criar() -> None:
            entrada = coletar_atividade(formulario, limites_do_evento(evento))
            if entrada is None:
                return
            ministrantes = seletor.coletar()
            if ministrantes is None:
                return
            entrada.ministrantes = ministrantes
            try:
                atividade = criar_atividade(evento.id, entrada)
            except HorarioAtividadeInvalido:
                ui.notify(
                    "O horário da atividade precisa estar contido no do evento.",
                    type="negative",
                )
                return
            except AtividadeSemMinistrante:
                ui.notify(
                    "A atividade precisa de pelo menos um ministrante.",
                    type="negative",
                )
                return
            except MinistranteRepetido:
                ui.notify(
                    "Um usuário não pode ministrar a mesma atividade duas vezes.",
                    type="negative",
                )
                return
            dialogo.close()
            ui.notify("Atividade criada.", type="positive")
            ui.navigate.to(f"/event/{evento.id}/activities/{atividade.id}")

        with ui.row().classes("w-full q-mt-md"):
            _ = ui.space()
            _ = ui.button("Cancelar", on_click=dialogo.close).props("flat")
            _ = ui.button("Criar", on_click=criar).props("color=primary")

    dialogo.open()


@pagina("/event/{evento_id}/activities")
def pagina_atividades(
    evento_id: int,
    usuario: Annotated[Usuario | None, Depends(obter_usuario_opcional)],
):
    try:
        evento = obter_evento(evento_id)
    except EventoNaoEncontrado:
        nao_encontrado(
            "event_busy", "Evento não encontrado", "/", "Voltar para a lista de eventos"
        )
        return

    eh_admin = eh_administrador(usuario)

    with ui.column().classes("w-full gap-4").style("max-width: 1000px; margin: 0 auto"):
        with ui.row().classes("w-full items-center"):
            _ = ui.link(f"← {evento.nome}", f"/event/{evento.id}").classes(
                "text-primary"
            )
            if eh_admin:
                _ = ui.space()
                _ = ui.button(
                    "Criar atividade",
                    icon="add",
                    on_click=lambda: _dialogo_criar_atividade(evento),
                ).props("color=primary")

        _ = ui.label("Atividades").classes("text-h5")

        @ui.refreshable
        def lista() -> None:
            atividades = listar_atividades(evento_id)
            if not atividades:
                _ = ui.label("Nenhuma atividade cadastrada.").classes("text-grey-7")
                return
            for atividade in atividades:
                _cartao_lista(evento, atividade)

        lista()

    voltar_ao_topo()


# --- Detalhes: edição e exclusão --------------------------------------------


def _dialogo_editar_atividade(evento: Evento, atividade: Atividade) -> None:
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
        with formulario_atividade(
            EntradaAtividade.de_atividade(atividade)
        ) as formulario:
            conectar_atividade(formulario, limites_do_evento(evento))

        def salvar() -> None:
            # validações de servidor: erros aparecem nos próprios campos
            valores = coletar_atividade(formulario, limites_do_evento(evento))
            if valores is None:
                return
            try:
                atividade.atualizar(**valores.parametros())
            except HorarioAtividadeInvalido:
                ui.notify(
                    "O horário da atividade precisa estar contido no do evento.",
                    type="negative",
                )
                return
            dialogo.close()
            ui.notify("Atividade atualizada.", type="positive")
            ui.navigate.to(f"/event/{evento.id}/activities/{atividade.id}")

        with ui.row().classes("w-full q-mt-md"):
            _ = ui.space()
            _ = ui.button("Cancelar", on_click=dialogo.close).props("flat")
            _ = ui.button("Salvar", on_click=salvar).props("color=primary")

    dialogo.open()


def _dialogo_excluir_atividade(evento: Evento, atividade: Atividade) -> None:
    """
    Dialog de confirmação da exclusão da atividade.

    A exclusão é bloqueada quando a atividade já recebeu presenças ou é a
    única do evento (regras de negócio); sem bloqueios, os vínculos de
    ministrantes são excluídos junto.
    """

    def confirmar(fechar: Callable[[], None]) -> None:
        try:
            removida = excluir_atividade(atividade.id)
        except AtividadeComDependencias:
            ui.notify(
                "Esta atividade já possui presenças registradas e não pode ser excluída.",
                type="negative",
            )
            fechar()
            return
        except EventoSemAtividade:
            ui.notify(
                "não é possível excluir a única atividade do evento.",
                type="negative",
            )
            fechar()
            return
        except AtividadeNaoEncontrada:
            ui.notify("Atividade não encontrada.", type="warning")
            fechar()
            return
        if not removida:
            ui.notify("Atividade não encontrada.", type="warning")
            return
        fechar()
        ui.notify("Atividade excluída.", type="positive")
        ui.navigate.to(f"/event/{evento.id}/activities")

    dialogo_confirmacao(
        "Excluir esta atividade?",
        "Os vínculos de ministrantes também serão excluídos. "
        "Esta ação não pode ser desfeita.",
        "Excluir",
        "negative",
        confirmar,
        marca="dialog-excluir-atividade",
    )


# --- Ministrantes -----------------------------------------------------------


def _cartao_ministrante(
    atividade: Atividade,
    ministrante: Ministrante,
    eh_admin: bool,
    atualizar: Callable[[], None],
) -> None:
    """Card de ministrante com as ações administrativas (editar/remover)."""
    with (
        ui.card().mark(f"ministrante-{ministrante.usuario.id}").classes("w-full"),
        ui.row().classes("w-full items-start gap-3"),
    ):
        _ = ui.icon("person", size="24px").classes("text-primary")
        with ui.column().classes("gap-0 flex-grow"):
            with ui.row().classes("items-center gap-2"):
                _ = ui.label(ministrante.usuario.nome).classes("text-weight-medium")
                _ = ui.label(ministrante.instituicao).classes("text-grey-7")
                if ministrante.link_lattes:
                    _ = ui.link("Lattes", ministrante.link_lattes, new_tab=True).props(
                        "flat dense no-caps color=primary"
                    )
            if ministrante.mini_bio:
                _ = ui.label(ministrante.mini_bio).classes("text-body2 text-grey-8")
        if eh_admin:
            _ = ui.button(
                "Editar dados",
                icon="edit",
                on_click=lambda: _dialogo_editar_ministrante(
                    atividade, ministrante, atualizar
                ),
            ).props("flat dense no-caps")
            _ = ui.button(
                "Remover",
                icon="delete",
                on_click=lambda: _dialogo_remover_ministrante(
                    atividade, ministrante, atualizar
                ),
            ).props("flat dense no-caps color=negative")


def _dialogo_editar_ministrante(
    atividade: Atividade, ministrante: Ministrante, atualizar: Callable[[], None]
) -> None:
    """
    Edita os dados do vínculo de um ministrante (instituição obrigatória,
    mini-bio e Lattes opcionais). O usuário em si não é alterado.
    """
    with (
        ui.dialog().mark("dialog-editar-ministrante") as dialogo,
        ui.card().classes("w-full").style("max-width: 500px"),
    ):
        _ = ui.label(f"Editar ministrante — {ministrante.usuario.nome}").classes(
            "text-h6"
        )
        instituicao = ui.input(
            "Instituição *",
            value=ministrante.instituicao,
            validation={"Informe a instituição.": obrigatorio},
        ).classes("w-full")
        mini_bio = ui.textarea("Mini-bio", value=ministrante.mini_bio or "").classes(
            "w-full"
        )
        link_lattes = ui.input(
            "Link do Lattes", value=ministrante.link_lattes or ""
        ).classes("w-full")

        def salvar() -> None:
            instituicao.validate()
            if campo_com_erro(instituicao):
                return
            atividade.atualizar_ministrante(
                usuario_id=ministrante.id_usuario,
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


def _dialogo_remover_ministrante(
    atividade: Atividade, ministrante: Ministrante, atualizar: Callable[[], None]
) -> None:
    """
    Dialog de confirmação antes de remover um ministrante (ação
    destrutiva; a regra impede a atividade de ficar sem ministrantes).
    """

    def confirmar(fechar: Callable[[], None]) -> None:
        try:
            removido = atividade.remover_ministrante(ministrante.id_usuario)
        except AtividadeSemMinistrante:
            ui.notify(
                "A atividade precisa de pelo menos um ministrante.",
                type="negative",
            )
            fechar()
            return
        if not removido:
            ui.notify("Ministrante não encontrado.", type="warning")
            atualizar()
            fechar()
            return
        fechar()
        ui.notify("Ministrante removido.", type="positive")
        atualizar()

    dialogo_confirmacao(
        "Remover ministrante?",
        f"{ministrante.usuario.nome} deixará de ministrar esta atividade. "
        "A atividade precisa de pelo menos um ministrante.",
        "Remover",
        "negative",
        confirmar,
        marca="dialog-remover-ministrante",
    )


def _dialogo_adicionar_ministrantes(
    atividade: Atividade, atualizar: Callable[[], None]
) -> None:
    """
    Dialog de adição de ministrantes: multiselect com os usuários que
    ainda não ministram a atividade e, para cada selecionado, os campos do
    vínculo.
    """
    existentes = {
        m.id_usuario for m in listar_ministrantes(atividade.id_evento, atividade.id)
    }
    candidatos = [u for u in listar_usuarios() if u.id not in existentes]
    if not candidatos:
        ui.notify("Todos os usuários já ministram esta atividade.")
        return

    with (
        ui.dialog().mark("dialog-adicionar-ministrantes") as dialogo,
        ui.card().classes("w-full").style("max-width: 700px"),
    ):
        _ = ui.label("Adicionar ministrantes").classes("text-h6")
        with seletor_ministrantes(candidatos) as seletor:
            pass

        def adicionar() -> None:
            ministrantes = seletor.coletar()
            if ministrantes is None:
                return
            try:
                atividade.adicionar_ministrantes(ministrantes)
            except MinistranteRepetido:
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


def _dialogo_remover_presenca(
    atividade: Atividade, participante: Usuario, atualizar: Callable[[], None]
) -> None:
    """Dialog de confirmação antes de desfazer a presença de um participante."""

    def confirmar(fechar: Callable[[], None]) -> None:
        try:
            remover_presenca(participante.id, atividade.id_evento, atividade.id)
        except PresencaNaoEncontrada:
            ui.notify(
                "Presença não encontrada (já removida em outra aba?).",
                type="warning",
            )
        else:
            ui.notify("Presença removida.", type="positive")
        fechar()
        atualizar()

    dialogo_confirmacao(
        "Remover presença?",
        f"A presença de {participante.nome} nesta atividade será desfeita. "
        "Esta ação não pode ser desfeita.",
        "Remover",
        "negative",
        confirmar,
        marca="dialog-remover-presenca",
    )


def _dialogo_registrar_presenca(
    atividade: Atividade, atualizar: Callable[[], None]
) -> None:
    """
    Dialog de registro de presença (administrador): lista somente os
    inscritos **confirmados** no evento que ainda não têm presença — o
    ``registrar_presenca`` exige inscrição confirmada, dentro das vagas da
    atividade e sem presença duplicada.
    """
    presentes_ids = {
        u.id for u in listar_presencas_atividade(atividade.id_evento, atividade.id)
    }
    candidatos = [
        u
        for u in listar_participantes(atividade.id_evento)
        if u.id not in presentes_ids
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
            for usuario_id in selecionados:
                try:
                    _ = registrar_presenca(
                        usuario_id, atividade.id_evento, atividade.id
                    )
                except PresencaRepetida:
                    continue  # presença já registrada (página desatualizada)
                except SemVagas:
                    ui.notify(
                        "As vagas de presença desta atividade acabaram.",
                        type="warning",
                    )
                    break
                except InscricaoNaoConfirmada:
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


@pagina("/event/{evento_id}/activities/{atividade_id}")
def pagina_atividade(
    evento_id: int,
    atividade_id: int,
    usuario: Annotated[Usuario | None, Depends(obter_usuario_opcional)],
):
    try:
        evento = obter_evento(evento_id)
    except EventoNaoEncontrado:
        nao_encontrado(
            "event_busy", "Evento não encontrado", "/", "Voltar para a lista de eventos"
        )
        return

    try:
        atividade = obter_atividade(atividade_id, evento_id)
    except AtividadeNaoEncontrada:
        nao_encontrado(
            "event_note",
            "Atividade não encontrada",
            f"/event/{evento_id}",
            "Voltar para o evento",
        )
        return

    eh_admin = eh_administrador(usuario)

    @ui.refreshable
    def secao_ministrantes() -> None:
        """Ministrantes da atividade; as ações administrativas aparecem junto."""
        ministrantes = listar_ministrantes(evento_id, atividade.id)
        _ = ui.label("Ministrantes").classes("text-h5")
        if not ministrantes:
            _ = ui.label("Nenhum ministrante cadastrado.").classes("text-grey-7")
        for ministrante in ministrantes:
            _cartao_ministrante(
                atividade, ministrante, eh_admin, secao_ministrantes.refresh
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
        presentes = listar_presencas_atividade(evento_id, atividade.id)
        ids_presentes = {u.id for u in presentes}
        candidatos = [
            u for u in listar_participantes(evento_id) if u.id not in ids_presentes
        ]

        _ = ui.label("Presenças").classes("text-h5")
        _ = ui.label(
            f"{len(presentes)} de {atividade.vagas} vaga(s) de presença preenchidas."
        ).classes("text-caption text-grey-7")

        if presentes:
            for participante in presentes:
                with (
                    ui.card().mark(f"presenca-{participante.id}").classes("w-full"),
                    ui.row().classes("w-full items-center gap-3"),
                ):
                    _ = ui.icon("check_circle", size="24px").classes("text-positive")
                    with ui.column().classes("gap-0 flex-grow"):
                        _ = ui.label(participante.nome).classes("text-subtitle1")
                    _ = ui.button(
                        "Remover presença",
                        icon="person_remove",
                        on_click=lambda u=participante: _dialogo_remover_presenca(
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
            _ = ui.link(f"← {evento.nome}", f"/event/{evento.id}").classes(
                "text-primary"
            )
            _ = ui.link("Atividades", f"/event/{evento.id}/activities").props(
                "flat dense no-caps color=primary"
            )
            if eh_admin:
                _ = ui.space()
                _ = (
                    ui.button(
                        "Editar",
                        icon="edit",
                        on_click=lambda: _dialogo_editar_atividade(evento, atividade),
                    )
                    .mark("botao-editar-atividade")
                    .props("flat dense no-caps")
                )
                _ = ui.button(
                    "Excluir",
                    icon="delete",
                    on_click=lambda: _dialogo_excluir_atividade(evento, atividade),
                ).props("flat dense no-caps color=negative")

        _ = ui.label(atividade.nome).classes("text-h4")

        with ui.card().classes("w-full"), ui.column().classes("w-full gap-2"):
            linha_de_icones(
                (
                    ("schedule", horario_atividade(atividade)),
                    ("meeting_room", atividade.sala),
                    ("event_seat", f"{atividade.vagas} vagas"),
                )
            )
            if atividade.descricao:
                _ = ui.label(atividade.descricao).classes("text-body1")

        secao_ministrantes()

        if eh_admin:
            secao_presenca()

    voltar_ao_topo()
