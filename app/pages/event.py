"""
Página de detalhes de um evento: banner, nome, descrição, data, localização,
valor, vagas disponíveis e a programação de atividades. Também abriga os
dialogs administrativos do evento: criação (com atividades e ministrantes),
edição e exclusão.

A página é pública: a seção de inscrição se adapta ao estado do usuário
(não logado, já inscrito, evento lotado) e abre um dialog para escolher
valor cheio ou meia-entrada e anexar o comprovante.
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from nicegui import events, ui
from nicegui.elements.upload_files import FileUpload

from app.auth import eh_administrador, obter_usuario_opcional
from app.database.repository.activity import (
    Atividade,
    EntradaAtividade,
    listar_atividades_com_ministrantes,
)
from app.database.repository.event import (
    Evento,
    criar_evento,
    obter_evento,
)
from app.database.repository.inscription_list import (
    inscrever_usuario_evento,
    obter_inscricao,
)
from app.database.repository.user import Usuario, listar_usuarios
from app.exceptions import (
    AtividadeSemMinistrante,
    ComprovanteNaoEhPdf,
    EventoComDependencias,
    EventoComInscricoes,
    EventoNaoEncontrado,
    EventoRepetido,
    HorarioAtividadeInvalido,
    IdadeAbaixoClassificacao,
    MinistranteRepetido,
    SemVagas,
    VagasAbaixoInscricoes,
)
from app.forms.atividade import (
    FormularioAtividade,
    coletar_atividade,
    conectar_atividade,
    formulario_atividade,
)
from app.forms.evento import (
    coletar_valores,
    conectar_validacao_evento,
    formulario_evento,
    limites_do_formulario,
)
from app.forms.ministrante import SeletorMinistrantes, seletor_ministrantes
from app.modelos import ValoresEvento
from app.pages.layout import (
    data_hora,
    dialogo_confirmacao,
    formatar_moeda,
    horario_atividade,
    linha_de_icones,
    nao_encontrado,
    pagina,
    upload_comprovante,
    voltar_ao_topo,
)


def _info(icone: str, titulo: str) -> ui.column:
    """Linha de informação com ícone; o conteúdo é adicionado pelo chamador."""
    with ui.row().classes("items-start no-wrap gap-3"):
        _ = ui.icon(icone, size="24px").classes("text-primary")
        coluna = ui.column().classes("gap-0")
        with coluna:
            _ = ui.label(titulo).classes("text-caption text-grey-7")
    return coluna


def _vagas(evento: Evento) -> None:
    disponiveis = max(evento.vagas - (evento.inscritas or 0), 0)
    with _info("event_seat", "Vagas"):
        if disponiveis == 0:
            _ = ui.label(f"Esgotado ({evento.vagas} vagas)").classes("text-negative")
        else:
            _ = ui.label(f"{disponiveis} de {evento.vagas} disponíveis")


def _valor(evento: Evento) -> None:
    with _info("attach_money", "Valor"):
        if evento.valor > 0:
            _ = ui.label(f"Cheio: {formatar_moeda(evento.valor)}")
            _ = ui.label(f"Meia-entrada: {formatar_moeda(evento.valor_meia)}").classes(
                "text-grey-7"
            )
        else:
            _ = ui.label("Evento gratuito").classes("text-positive")


def _localizacao(evento: Evento) -> None:
    if evento.latitude is None or evento.longitude is None:
        _ = ui.label("Não informada").classes("text-grey-7")
        return
    # os tiles do mapa são carregados do OpenStreetMap pelo navegador
    mapa = ui.leaflet(center=(evento.latitude, evento.longitude), zoom=15).classes(
        "w-full h-64 rounded-borders"
    )
    _ = mapa.marker(latlng=(evento.latitude, evento.longitude))


def _cartao_atividade(atividade: Atividade) -> None:
    with ui.card().classes("w-full"), ui.column().classes("w-full gap-2"):
        _ = ui.link(
            atividade.nome,
            f"/event/{atividade.id_evento}/activities/{atividade.id}",
        ).classes("text-h6 text-weight-medium no-underline text-inherit")
        linha_de_icones(
            (
                ("schedule", horario_atividade(atividade)),
                ("meeting_room", atividade.sala),
                ("event_seat", f"{atividade.vagas} vagas"),
            )
        )
        if atividade.descricao:
            _ = ui.label(atividade.descricao).classes("text-body1")

        # página pública: dos ministrantes só são exibidos dados de
        # apresentação, nunca CPF ou e-mail
        _ = ui.label("Ministrantes").classes("text-caption text-grey-7 q-mt-sm")
        for ministrante in atividade.ministrantes:
            with ui.row().classes("items-start no-wrap gap-2"):
                _ = ui.icon("person", size="20px").classes("text-primary")
                with ui.column().classes("gap-0"):
                    with ui.row().classes("items-center gap-2"):
                        _ = ui.label(ministrante.usuario.nome).classes(
                            "text-weight-medium"
                        )
                        _ = ui.label(ministrante.instituicao).classes("text-grey-7")
                        if ministrante.link_lattes:
                            _ = ui.link("Lattes", ministrante.link_lattes, new_tab=True)
                    if ministrante.mini_bio:
                        _ = ui.label(ministrante.mini_bio).classes(
                            "text-body2 text-grey-8"
                        )


def _atividades(evento_id: int) -> None:
    atividades = listar_atividades_com_ministrantes(evento_id)
    with ui.row().classes("w-full items-center"):
        _ = ui.label("Atividades").classes("text-h5")
        _ = ui.space()
        _ = ui.link(
            "Ver todas as atividades",
            f"/event/{evento_id}/activities",
        ).props("flat dense no-caps color=primary")
    if not atividades:
        _ = ui.label("Nenhuma atividade cadastrada.").classes("text-grey-7")
        return
    for atividade in atividades:
        _cartao_atividade(atividade)


def _dialogo_inscricao(evento: Evento, usuario: Usuario) -> None:
    """
    Dialog de inscrição: o usuário escolhe valor cheio ou meia-entrada e
    anexa o comprovante (que também justifica a meia-entrada). O valor é
    derivado do preço do evento — o usuário nunca digita o valor.

    Evento gratuito não tem nem escolha de valor nem comprovante.
    """
    gratuita = evento.valor == 0
    arquivo: FileUpload | None = None

    def arquivo_selecionado(e: events.UploadEventArguments):
        nonlocal arquivo
        arquivo = e.file
        erro_comprovante.visible = False

    with ui.dialog() as dialogo, ui.card().classes("w-full").style("max-width: 500px"):
        _ = ui.label(f"Inscrever-se em {evento.nome}").classes("text-h6")

        radios = None
        if gratuita:
            _ = ui.label("Este evento é gratuito, é só confirmar a inscrição.").classes(
                "text-body2 text-grey-7 q-mb-md"
            )
        else:
            radios = ui.radio(
                {
                    "cheio": f"Valor cheio — {formatar_moeda(evento.valor)}",
                    "meia": f"Meia-entrada — {formatar_moeda(evento.valor_meia)}",
                },
                value="cheio",
            ).classes("w-full q-mb-md")

            _ = ui.label(
                "Comprovante de pagamento em pdf, para a meia-entrada inclua um documento válido no mesmo arquivo"
            ).classes("text-caption text-grey-7")

            _ = upload_comprovante(on_upload=arquivo_selecionado)
            erro_comprovante = ui.label(
                "Anexe o comprovante em PDF para confirmar a inscrição."
            ).classes("text-negative text-caption")
            erro_comprovante.visible = False

        async def enviar() -> None:
            if not gratuita and not arquivo:
                erro_comprovante.visible = True
                return
            try:
                _ = inscrever_usuario_evento(
                    usuario_id=usuario.id,
                    evento_id=evento.id,
                    meia=radios.value == "meia" if radios else False,
                    comprovante_usuario=await arquivo.read() if arquivo else None,
                )
            except EventoRepetido:
                ui.notify("Você já possui uma inscrição neste evento.")
                return
            except IdadeAbaixoClassificacao:
                ui.notify(f"""
                Sua idade não permite a inscrição neste evento
                (classificação {evento.classificacao_indicativa}+)
                """)
                return
            except SemVagas:
                ui.notify("As vagas deste evento acabaram.")
                return
            except ComprovanteNaoEhPdf:
                ui.notify("O comprovante precisa ser um arquivo PDF.")
                return
            ui.navigate.to(f"/user/registrations/{evento.id}")

        with ui.row().classes("w-full"):
            _ = ui.space()
            _ = ui.button("Voltar", on_click=dialogo.close).props("flat")
            _ = ui.button("Inscrever-se", on_click=enviar).props("color=primary")

    dialogo.open()


def _secao_inscricao(evento: Evento, usuario: Usuario | None) -> None:
    """Botão de inscrição adaptado ao estado do usuário."""
    with ui.card().classes("w-full"), ui.row().classes("w-full items-center gap-3"):
        _ = ui.icon("how_to_reg", size="28px").classes("text-primary")
        if usuario is None:
            _ = ui.label("Faça login para se inscrever neste evento.").classes(
                "text-body1"
            )
            _ = ui.space()
            _ = ui.link("Entrar", "/login").props("flat dense no-caps color=primary")
            return

        existente = obter_inscricao(usuario.id, evento.id)
        if existente is not None and existente.status != "cancelada":
            _ = ui.label(f"Sua inscrição está {existente.status.lower()}.").classes(
                "text-body1"
            )
            _ = ui.space()
            _ = ui.link(
                "Ver minha inscrição",
                f"/user/registrations/{evento.id}",
            ).props("flat dense no-caps color=primary")
            return

        if existente is not None:  # cancelada: não é possível re-inscrever (PK)
            _ = ui.label("Sua inscrição neste evento foi cancelada.").classes(
                "text-body1"
            )
            _ = ui.space()
            _ = ui.link(
                "Ver detalhes",
                f"/user/registrations/{evento.id}",
            ).props("flat dense no-caps color=primary")
            return

        if (evento.inscritas or 0) >= evento.vagas:
            _ = ui.button("Evento lotado", icon="event_busy").props("outline").disable()
            return

        _ = ui.label("Garanta sua vaga").classes("text-body1")
        _ = ui.space()
        _ = ui.button(
            "Inscrever-se",
            icon="how_to_reg",
            on_click=lambda: _dialogo_inscricao(evento, usuario),
        ).props("color=primary")


def dialogo_criar_evento(ao_sucesso: Callable[[int], None]) -> None:
    """
    Dialog administrativo de criação de evento.

    O evento precisa ter pelo menos uma atividade (regra de negócio), então
    o dialog também lista as atividades a criar; cada uma precisa estar
    contida no horário do evento e ter ao menos um ministrante. Ao concluir,
    ``ao_sucesso`` recebe o id do evento criado.
    """
    linhas: list[tuple[ui.card, FormularioAtividade, SeletorMinistrantes]] = []
    revalidadores: list[Callable[[], None]] = []
    usuarios = listar_usuarios()

    with ui.dialog() as dialogo, ui.card().classes("w-full").style("max-width: 900px"):
        _ = ui.label("Criar evento").classes("text-h6")
        with formulario_evento() as formulario:
            # validações de múltiplos campos do evento (datas e lat/lng)
            # exibidas inline, como as validações por campo
            conectar_validacao_evento(formulario)

        with ui.separator():
            pass

        _ = ui.label("Atividades (pelo menos uma)").classes("text-subtitle1")
        with ui.column().classes("w-full gap-2") as container_atividades:
            pass

        def adicionar_linha() -> None:
            with container_atividades:
                cartao = ui.card().classes("w-full")
                with cartao:
                    with formulario_atividade() as formulario_ativ:
                        pass
                    _ = ui.label("Ministrantes (pelo menos um)").classes(
                        "text-caption text-grey-7 q-mt-sm"
                    )
                    with seletor_ministrantes(usuarios) as seletor:
                        pass
            entrada = (cartao, formulario_ativ, seletor)

            def remover() -> None:
                linhas.remove(entrada)
                cartao.delete()

            with cartao:
                with ui.row().classes("w-full"):
                    _ = ui.space()
                    _ = ui.button(
                        "Remover atividade", icon="delete", on_click=remover
                    ).props("flat dense no-caps color=negative")

            linhas.append(entrada)
            # validação inline "atividade contida no horário do evento"
            revalidadores.append(
                conectar_atividade(formulario_ativ, limites_do_formulario(formulario))
            )

        adicionar_linha()

        # mudanças no horário do evento reavaliam a contenção de todas as linhas
        for campo in (
            formulario.data_inicio,
            formulario.hora_inicio,
            formulario.data_fim,
            formulario.hora_fim,
        ):
            campo.on_value_change(
                lambda _: [revalidar() for revalidar in revalidadores]
            )

        _ = ui.button(
            "Adicionar atividade", icon="add", on_click=adicionar_linha
        ).props("flat dense no-caps")

        def criar() -> None:
            # validações de servidor: erros aparecem nos próprios campos
            valores = coletar_valores(formulario)
            if valores is None:
                return

            if not linhas:
                ui.notify("Adicione pelo menos uma atividade.")
                return

            atividades: list[EntradaAtividade] = []
            for _, formulario_ativ, seletor in linhas:
                entrada = coletar_atividade(
                    formulario_ativ, limites_do_formulario(formulario)
                )
                if entrada is None:
                    return  # erro exibido nos campos da linha
                ministrantes = seletor.coletar()
                if ministrantes is None:
                    return  # erro exibido no seletor da linha
                entrada.ministrantes = ministrantes
                atividades.append(entrada)

            try:
                evento = criar_evento(**valores.parametros(), atividades=atividades)
            except EventoRepetido:
                ui.notify("Já existe um evento com esse nome.")
                return
            except HorarioAtividadeInvalido:
                ui.notify(
                    "O horário de cada atividade precisa estar contido no do evento."
                )
                return
            except AtividadeSemMinistrante:
                ui.notify("Cada atividade precisa de pelo menos um ministrante.")
                return
            except MinistranteRepetido:
                ui.notify("Um usuário não pode ministrar a mesma atividade duas vezes.")
                return
            dialogo.close()
            ao_sucesso(evento.id)

        with ui.row().classes("w-full q-mt-md"):
            _ = ui.space()
            _ = ui.button("Cancelar", on_click=dialogo.close).props("flat")
            _ = ui.button("Criar", on_click=criar).props("color=primary")

    dialogo.open()


def dialogo_editar_evento(evento: Evento) -> None:
    """
    Dialog administrativo de edição de evento, pré-preenchido.

    O salvamento delega as regras de negócio ao ``Evento.atualizar``: vagas
    não podem ficar abaixo das inscrições ativas e o novo horário precisa
    continuar contendo as atividades existentes.
    """
    with ui.dialog() as dialogo, ui.card().classes("w-full").style("max-width: 900px"):
        _ = ui.label(f"Editar {evento.nome}").classes("text-h6")
        with formulario_evento(ValoresEvento.de_evento(evento)) as formulario:
            # validações de múltiplos campos (datas e lat/lng) exibidas inline
            conectar_validacao_evento(formulario)
        if (evento.inscritas or 0) > 0:
            _ = ui.label(
                f"Evento com {evento.inscritas} inscrição(ões) ativa(s): "
                "as vagas não podem ficar abaixo desse número."
            ).classes("text-caption text-grey-7")

        def salvar() -> None:
            # validações de servidor: erros aparecem nos próprios campos
            valores = coletar_valores(formulario)
            if valores is None:
                return
            try:
                evento.atualizar(**valores.parametros())
            except VagasAbaixoInscricoes:
                ui.notify(
                    "As vagas não podem ficar menores que o número de "
                    "inscrições ativas.",
                    type="negative",
                )
                return
            except HorarioAtividadeInvalido:
                ui.notify(
                    "O novo horário precisa continuar contendo as atividades "
                    "do evento.",
                    type="negative",
                )
                return
            except EventoRepetido:
                ui.notify("Já existe um evento com esse nome.", type="negative")
                return
            dialogo.close()
            ui.notify("Evento atualizado.", type="positive")
            ui.navigate.to(f"/event/{evento.id}")

        with ui.row().classes("w-full q-mt-md"):
            _ = ui.space()
            _ = ui.button("Cancelar", on_click=dialogo.close).props("flat")
            _ = ui.button("Salvar", on_click=salvar).props("color=primary")

    dialogo.open()


def _dialogo_excluir_evento(evento: Evento) -> None:
    """
    Dialog de confirmação da exclusão de um evento.

    A exclusão é bloqueada quando o evento possui ao menos uma inscrição
    (regra de negócio); sem inscrições, as atividades e os ministrantes são
    excluídos junto.
    """

    def confirmar(fechar: Callable[[], None]) -> None:
        try:
            removido = evento.excluir()
        except EventoComInscricoes:
            ui.notify(
                "Este evento possui usuários inscritos e não pode ser excluído.",
                type="negative",
            )
            return
        except EventoComDependencias:
            ui.notify("Não foi possível excluir o evento.", type="negative")
            return
        if not removido:
            ui.notify("Evento não encontrado.", type="warning")
            return
        fechar()
        ui.notify("Evento excluído.", type="positive")
        ui.navigate.to("/")

    dialogo_confirmacao(
        "Excluir este evento?",
        "As atividades e os ministrantes do evento também serão "
        "excluídos. Esta ação não pode ser desfeita.",
        "Excluir",
        "negative",
        confirmar,
    )


# página pública: não exige login
@pagina("/event/{evento_id}")
def pagina_evento(
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
        with ui.row().classes("w-full items-center gap-1"):
            _ = ui.link("← Eventos", "/").classes("text-primary")
            if eh_admin:
                _ = ui.space()
                _ = ui.link(
                    "Inscrições",
                    f"/event/{evento.id}/registrations",
                ).props("flat dense no-caps")

        if evento.banner:
            _ = (
                ui.image(evento.banner)
                .classes("w-full rounded-borders")
                .style("aspect-ratio: 3 / 1")
            )
        if eh_admin:
            with ui.row().classes("w-full items-center gap-1"):
                _ = ui.label(evento.nome).classes("text-h4")
                _ = ui.space()
                _ = ui.button(
                    "Editar",
                    icon="edit",
                    on_click=lambda: dialogo_editar_evento(evento),
                ).props("flat dense no-caps")

        _ = ui.label(evento.descricao or "").classes("text-body1")

        _secao_inscricao(evento, usuario)

        _atividades(evento.id)

        with ui.card().classes("w-full"), ui.column().classes("w-full gap-4"):
            with _info("schedule", "Data"):
                _ = ui.label(f"Início: {data_hora(evento.data_hora_inicio)}")
                _ = ui.label(f"Fim: {data_hora(evento.data_hora_fim)}")
            _vagas(evento)
            _valor(evento)
            _localizacao(evento)
        if eh_admin:
            with ui.row().classes("w-full items-center gap-1"):
                _ = ui.space()
                _ = ui.button(
                    "Excluir",
                    icon="delete",
                    on_click=lambda: _dialogo_excluir_evento(evento),
                ).props("dense no-caps color=negative ")
                _ = ui.space()

    voltar_ao_topo()
