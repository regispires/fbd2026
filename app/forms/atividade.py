"""
Formulário de atividade: context manager com os campos comuns aos dialogs
de criação e edição de atividades, a conexão das datas com o intervalo do
evento e a coleta validada dos valores (``EntradaAtividade``).

A validação de contenção no evento e a coleta são parametrizadas por um
``limites`` callable — lido no momento da validação — o que permite
reutilizar as mesmas funções no dialog de criação (limites vindos dos
campos do evento, via ``limites_do_formulario``) e no de edição (limites
fixos do evento carregado, via ``limites_do_evento``).
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime

from nicegui import ui

from app.database.repository import contido_em
from app.database.repository.activity import EntradaAtividade
from app.database.repository.event import Evento
from app.forms.validacao import (
    campo_com_erro,
    campo_data,
    limitar_calendario,
    mostrar_erro,
    obrigatorio,
    validar_extremo,
    vazio_para_none,
)


@dataclass
class FormularioAtividade:
    """Referências aos campos de um formulário de atividade."""

    nome: ui.input
    descricao: ui.textarea
    sala: ui.input
    vagas: ui.number
    data_inicio: ui.date_input
    hora_inicio: ui.time_input
    data_fim: ui.date_input
    hora_fim: ui.time_input


@contextmanager
def formulario_atividade(
    valores: EntradaAtividade | None = None,
) -> Iterator[FormularioAtividade]:
    """
    Renderiza os campos de uma atividade no container atual e devolve as
    referências.

    ``valores`` pré-preenche os campos (edição); ``None`` usa valores
    iniciais neutros (criação).
    """
    v = valores

    with ui.column().classes("w-full gap-2"):
        nome = ui.input(
            "Nome da atividade *",
            value=v.nome if v else "",
            validation={"Informe o nome da atividade.": obrigatorio},
        ).classes("w-full")
        descricao = ui.textarea(
            "Descrição (opcional)",
            value=v.descricao or "" if v else "",
        ).classes("w-full")
        with ui.row().classes("w-full gap-4 items-start"):
            sala = ui.input(
                "Sala *",
                value=v.sala if v else "",
                validation={"Informe a sala da atividade.": obrigatorio},
            ).classes("flex-grow")
            vagas = ui.number(
                "Vagas *",
                min=1,
                value=v.vagas if v else 10,
                validation={
                    "A atividade precisa de pelo menos uma vaga.": lambda x: (
                        x is not None and x >= 1
                    )
                },
            ).classes("w-28")
        with ui.row().classes("w-full gap-4 items-start"):
            data_inicio = campo_data(
                "Data de início *",
                v.data_hora_inicio.strftime("%d/%m/%Y") if v else "",
            ).classes("flex-grow")
            hora_inicio = ui.time_input(
                "Hora de início *",
                value=v.data_hora_inicio.strftime("%H:%M") if v else "",
            ).classes("w-40")
            data_fim = campo_data(
                "Data de fim *",
                v.data_hora_fim.strftime("%d/%m/%Y") if v else "",
            ).classes("flex-grow")
            hora_fim = ui.time_input(
                "Hora de fim *",
                value=v.data_hora_fim.strftime("%H:%M") if v else "",
            ).classes("w-40")

        formulario = FormularioAtividade(
            nome=nome,
            descricao=descricao,
            sala=sala,
            vagas=vagas,
            data_inicio=data_inicio,
            hora_inicio=hora_inicio,
            data_fim=data_fim,
            hora_fim=hora_fim,
        )
        yield formulario


def limites_do_evento(
    evento: Evento,
) -> Callable[[], tuple[datetime | None, datetime | None]]:
    """Intervalo fixo de um evento já carregado (dialogs de edição e de criação em evento existente)."""

    def limites() -> tuple[datetime | None, datetime | None]:
        return (evento.data_hora_inicio, evento.data_hora_fim)

    return limites


def conectar_atividade(
    formulario: FormularioAtividade,
    limites: Callable[[], tuple[datetime | None, datetime | None]],
) -> Callable[[], None]:
    """
    Liga as datas da atividade a um par de limites do evento **lido no
    momento da validação**: mudanças na atividade reavaliam preenchimento,
    início anterior ao fim e contenção no evento, exibindo os erros nos
    campos.

    Os calendários dos campos de data também são restringidos ao intervalo
    (props do QDate): reavaliar reaplica os limites, o que acompanha
    intervalos dinâmicos (campos do evento no dialog de criação).

    Retorna o revalidator, para o dialog revalidar as linhas quando o
    horário do evento mudar.
    """
    campos = (
        formulario.data_inicio,
        formulario.hora_inicio,
        formulario.data_fim,
        formulario.hora_fim,
    )

    def limitar_calendarios() -> None:
        """Aplica o intervalo corrente do evento aos pickers de data."""
        inicio_evento, fim_evento = limites()
        for campo in (formulario.data_inicio, formulario.data_fim):
            limitar_calendario(campo, inicio_evento, fim_evento)

    limitar_calendarios()  # já na abertura (no dialog de edição os limites são fixos)

    def revalidar() -> None:
        limitar_calendarios()
        inicio = validar_extremo(
            formulario.data_inicio,
            formulario.hora_inicio,
            "Informe a data de início.",
            "Informe a hora de início.",
        )
        fim = validar_extremo(
            formulario.data_fim,
            formulario.hora_fim,
            "Informe a data de fim.",
            "Informe a hora de fim.",
        )
        if inicio is None or fim is None:
            return
        if fim <= inicio:
            mostrar_erro(
                formulario.data_fim,
                "O início da atividade precisa ser anterior ao fim.",
            )
            return
        mostrar_erro(formulario.data_fim, None)

        inicio_evento, fim_evento = limites()
        if (
            inicio_evento is not None
            and fim_evento is not None
            and not contido_em(inicio, fim, inicio_evento, fim_evento)
        ):
            mostrar_erro(
                formulario.data_inicio,
                "A atividade precisa estar contida no horário do evento.",
            )
            mostrar_erro(
                formulario.data_fim,
                "A atividade precisa estar contida no horário do evento.",
            )
            return
        mostrar_erro(formulario.data_inicio, None)

    for campo in campos:
        campo.on_value_change(lambda _: revalidar())
    return revalidar


def coletar_atividade(
    formulario: FormularioAtividade,
    limites: Callable[[], tuple[datetime | None, datetime | None]],
) -> EntradaAtividade | None:
    """
    Validação de servidor do formulário de atividade contra um intervalo de
    evento **lido no momento da validação** (a reexecução das regras,
    exibida nos próprios campos — ver ``coletar_valores`` do evento).
    Devolve ``None`` quando inválido.
    """
    formulario.nome.validate()
    formulario.sala.validate()
    formulario.vagas.validate()

    inicio = validar_extremo(
        formulario.data_inicio,
        formulario.hora_inicio,
        "Informe a data de início.",
        "Informe a hora de início.",
    )
    fim = validar_extremo(
        formulario.data_fim,
        formulario.hora_fim,
        "Informe a data de fim.",
        "Informe a hora de fim.",
    )
    if inicio is not None and fim is not None:
        if fim <= inicio:
            mostrar_erro(
                formulario.data_fim,
                "O início da atividade precisa ser anterior ao fim.",
            )
        else:
            inicio_evento, fim_evento = limites()
            if (
                inicio_evento is not None
                and fim_evento is not None
                and not contido_em(inicio, fim, inicio_evento, fim_evento)
            ):
                mostrar_erro(
                    formulario.data_inicio,
                    "A atividade precisa estar contida no horário do evento.",
                )
                mostrar_erro(
                    formulario.data_fim,
                    "A atividade precisa estar contida no horário do evento.",
                )
            else:
                mostrar_erro(formulario.data_inicio, None)
                mostrar_erro(formulario.data_fim, None)

    campos_com_erro = (
        formulario.nome,
        formulario.sala,
        formulario.vagas,
        formulario.data_inicio,
        formulario.hora_inicio,
        formulario.data_fim,
        formulario.hora_fim,
    )
    if any(campo_com_erro(campo) for campo in campos_com_erro):
        return None

    return EntradaAtividade(
        nome=(formulario.nome.value or "").strip(),
        descricao=vazio_para_none(formulario.descricao.value),
        sala=(formulario.sala.value or "").strip(),
        vagas=int(formulario.vagas.value or 0),
        data_hora_inicio=inicio,
        data_hora_fim=fim,
    )
