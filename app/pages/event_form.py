"""
Campos de formulário compartilhados entre os dialogs de criação e edição
de eventos, e a sub-forma de atividades do dialog de criação.

Padronização dos formulários:

- rótulos de campos obrigatórios terminam com ``*``;
- validações de um único campo usam o argumento ``validation`` do próprio
  controle (NiceGUI mostra o erro imediatamente sob o campo);
- validações que envolvem mais de um campo (data com hora, início/fim,
  atividade contida no evento, par latitude/longitude) são ligadas a
  ``on_value_change`` e exibem o erro nos campos da mesma forma (via
  ``error``/``error-message``);
- a validação final permanece no servidor, em ``coletar_valores`` e
  ``coletar_atividade``: em vez de devolver mensagens soltas, elas mostram
  os erros nos próprios campos e devolvem ``None`` quando o formulário
  está inválido.

O banner e o thumbnail são URLs informadas pelo administrador (não existe
upload de arquivo). Datas e horários usam ``ui.date_input``/``ui.time_input``
(dias em dia/mês/ano e horas em HH:MM) e são combinados em ``datetime`` na coleta.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any

from nicegui import ui
from nicegui.elements.mixins.validation_element import ValidationElement

from app.database.repository.event import Event


# classificação indicativa -> rótulo do select; None = sem restrição de idade
# (em ui.select com dict, as chaves são os valores armazenados e os valores
# de cada entrada são os rótulos exibidos)
CLASSIFICACOES = {
    None: "Sem restrição",
    10: "10 anos",
    12: "12 anos",
    14: "14 anos",
    16: "16 anos",
    18: "18 anos",
}


def _obrigatorio(valor: Any) -> bool:
    """Regra de obrigatoriedade para o ``validation`` (aplica ``strip`` em texto)."""
    if isinstance(valor, str):
        return bool(valor.strip())
    return valor is not None


def _campo_data(label: str, value: str = "") -> ui.date_input:
    """Campo de data (dia/mês/ano); o picker emite o mesmo formato do campo."""
    campo = ui.date_input(label, value=value)
    campo.picker.props('mask="DD/MM/YYYY"')
    return campo


@dataclass
class EventFormValues:
    """Valores validados do formulário de evento, prontos para o repositório."""

    nome: str
    descricao: str | None
    data_hora_inicio: datetime
    data_hora_fim: datetime
    classificacao_indicativa: int | None
    vagas: int
    valor: float
    latitude: float | None
    longitude: float | None
    banner: str | None
    banner_thumbnail: str | None


@dataclass
class EventForm:
    """Referências aos campos de um formulário de evento."""

    nome: ui.input
    descricao: ui.textarea
    data_inicio: ui.date_input
    hora_inicio: ui.time_input
    data_fim: ui.date_input
    hora_fim: ui.time_input
    classificacao: ui.select
    vagas: ui.number
    valor: ui.number
    latitude: ui.number
    longitude: ui.number
    banner: ui.input
    banner_thumbnail: ui.input


@dataclass
class AtividadeFormValues:
    """Valores validados de uma linha de atividade do dialog de criação."""

    nome: str
    descricao: str | None
    sala: str
    vagas: int
    data_hora_inicio: datetime
    data_hora_fim: datetime


@dataclass
class ActivityForm:
    """Referências aos campos de uma linha de atividade."""

    nome: ui.input
    descricao: ui.textarea
    sala: ui.input
    vagas: ui.number
    data_inicio: ui.date_input
    hora_inicio: ui.time_input
    data_fim: ui.date_input
    hora_fim: ui.time_input


def valores_evento(event: Event) -> EventFormValues:
    """Converte um ``Event`` em valores para pré-preencher o formulário de edição."""
    return EventFormValues(
        nome=event.nome,
        descricao=event.descricao,
        data_hora_inicio=event.data_hora_inicio,
        data_hora_fim=event.data_hora_fim,
        classificacao_indicativa=event.classificacao_indicativa,
        vagas=event.vagas,
        valor=event.valor,
        latitude=event.latitude,
        longitude=event.longitude,
        banner=event.banner,
        banner_thumbnail=event.banner_thumbnail,
    )


def campos_evento(valores: EventFormValues | None = None) -> EventForm:
    """
    Renderiza os campos comuns de evento no container atual.

    ``valores`` pré-preenche os campos (edição); ``None`` usa valores
    iniciais neutros (criação).
    """
    v = valores

    with ui.column().classes("w-full gap-2"):
        nome = ui.input(
            "Nome *",
            value=v.nome if v else "",
            validation={"Informe o nome do evento.": _obrigatorio},
        ).classes("w-full")
        descricao = ui.textarea(
            "Descrição", value=v.descricao or "" if v else ""
        ).classes("w-full")
        with ui.row().classes("w-full gap-2 items-start"):
            data_inicio = _campo_data(
                "Data de início *",
                v.data_hora_inicio.strftime("%d/%m/%Y") if v else "",
            )
            hora_inicio = ui.time_input(
                "Hora de início *",
                value=v.data_hora_inicio.strftime("%H:%M") if v else "",
            ).classes("w-40")

            _ = ui.space()

            data_fim = _campo_data(
                "Data de fim *",
                v.data_hora_fim.strftime("%d/%m/%Y") if v else "",
            )
            hora_fim = ui.time_input(
                "Hora de fim *",
                value=v.data_hora_fim.strftime("%H:%M") if v else "",
            ).classes("w-40")
        with ui.row().classes("w-full gap-4 items-start"):
            classificacao = ui.select(
                CLASSIFICACOES,
                label="Classificação indicativa",
                value=v.classificacao_indicativa if v else None,
            ).classes("flex-grow")
            vagas = ui.number(
                "Vagas *",
                min=1,
                value=v.vagas if v else 1,
                validation={
                    "O evento precisa de pelo menos uma vaga.": lambda x: x is not None and x >= 1
                },
            ).classes("w-28")
            valor = ui.number(
                "Valor (R$) *",
                min=0,
                value=v.valor if v else 0,
                validation={
                    "Informe o valor (0 para evento gratuito).": lambda x: x is not None and x >= 0
                },
            ).classes("w-36")
        with ui.row().classes("w-full gap-4 items-start"):
            latitude = ui.number("Latitude", value=v.latitude if v else None).classes(
                "flex-grow"
            )
            longitude = ui.number(
                "Longitude", value=v.longitude if v else None
            ).classes("flex-grow")
        banner = ui.input("Banner (URL)", value=(v.banner or "") if v else "").classes(
            "w-full"
        )
        banner_thumbnail = ui.input(
            "Thumbnail (URL)", value=(v.banner_thumbnail or "") if v else ""
        ).classes("w-full")

    return EventForm(
        nome=nome,
        descricao=descricao,
        data_inicio=data_inicio,
        hora_inicio=hora_inicio,
        data_fim=data_fim,
        hora_fim=hora_fim,
        classificacao=classificacao,
        vagas=vagas,
        valor=valor,
        latitude=latitude,
        longitude=longitude,
        banner=banner,
        banner_thumbnail=banner_thumbnail,
    )


def linha_atividade() -> ActivityForm:
    """Renderiza os campos de uma atividade no container atual."""
    with ui.column().classes("w-full gap-2"):
        nome = ui.input(
            "Nome da atividade *",
            validation={"Informe o nome da atividade.": _obrigatorio},
        ).classes("w-full")
        descricao = ui.textarea("Descrição (opcional)").classes("w-full")
        with ui.row().classes("w-full gap-4 items-start"):
            sala = ui.input(
                "Sala *",
                validation={"Informe a sala da atividade.": _obrigatorio},
            ).classes("flex-grow")
            vagas = ui.number(
                "Vagas *",
                min=1,
                value=10,
                validation={
                    "A atividade precisa de pelo menos uma vaga.": lambda x: x is not None and x >= 1
                },
            ).classes("w-28")
        with ui.row().classes("w-full gap-4 items-start"):
            data_inicio = _campo_data("Data de início *").classes("flex-grow")
            hora_inicio = ui.time_input("Hora de início *").classes("w-40")
            data_fim = _campo_data("Data de fim *").classes("flex-grow")
            hora_fim = ui.time_input("Hora de fim *").classes("w-40")

    return ActivityForm(
        nome=nome,
        descricao=descricao,
        sala=sala,
        vagas=vagas,
        data_inicio=data_inicio,
        hora_inicio=hora_inicio,
        data_fim=data_fim,
        hora_fim=hora_fim,
    )


def conectar_validacao_evento(form: EventForm) -> None:
    """
    Liga as validações do evento que envolvem mais de um campo (data+hora
    de cada extremidade, início anterior ao fim e par latitude/longitude)
    às mudanças dos campos, exibindo os erros como as validações por campo.
    """

    def revalidar_datas() -> None:
        inicio = _validar_extremo(
            form.data_inicio,
            form.hora_inicio,
            "Informe a data de início.",
            "Informe a hora de início.",
        )
        fim = _validar_extremo(
            form.data_fim,
            form.hora_fim,
            "Informe a data de fim.",
            "Informe a hora de fim.",
        )
        if inicio is not None and fim is not None:
            mostrar_erro(
                form.data_fim,
                "O início do evento precisa ser anterior ao fim."
                if fim <= inicio
                else None,
            )

    def revalidar_lat_lng() -> None:
        lat = form.latitude.value
        lng = form.longitude.value
        erro = (
            "Informe latitude e longitude juntas, ou deixe ambas em branco."
            if (lat is None) != (lng is None)
            else None
        )
        mostrar_erro(form.latitude, erro)
        mostrar_erro(form.longitude, erro)

    for campo in (form.data_inicio, form.hora_inicio, form.data_fim, form.hora_fim):
        campo.on_value_change(lambda _: revalidar_datas())
    form.latitude.on_value_change(lambda _: revalidar_lat_lng())
    form.longitude.on_value_change(lambda _: revalidar_lat_lng())


def conectar_atividade(
    atividade: ActivityForm, evento: EventForm
) -> Callable[[], None]:
    """
    Liga as datas da atividade ao intervalo do evento: mudanças na
    atividade ou no horário do evento reavaliam preenchimento, início
    anterior ao fim e contenção no evento, exibindo os erros nos campos.

    Retorna o revalidator, para o dialog revalidar as linhas quando o
    horário do evento mudar.
    """
    campos = (
        atividade.data_inicio,
        atividade.hora_inicio,
        atividade.data_fim,
        atividade.hora_fim,
    )

    def revalidar() -> None:
        inicio = _validar_extremo(
            atividade.data_inicio,
            atividade.hora_inicio,
            "Informe a data de início.",
            "Informe a hora de início.",
        )
        fim = _validar_extremo(
            atividade.data_fim,
            atividade.hora_fim,
            "Informe a data de fim.",
            "Informe a hora de fim.",
        )
        if inicio is None or fim is None:
            return
        if fim <= inicio:
            mostrar_erro(
                atividade.data_fim,
                "O início da atividade precisa ser anterior ao fim.",
            )
            return
        mostrar_erro(atividade.data_fim, None)

        inicio_evento = _ler_data_hora(
            evento.data_inicio.value, evento.hora_inicio.value
        )
        fim_evento = _ler_data_hora(evento.data_fim.value, evento.hora_fim.value)
        if (
            inicio_evento is not None
            and fim_evento is not None
            and (inicio < inicio_evento or fim > fim_evento)
        ):
            mostrar_erro(
                atividade.data_inicio,
                "A atividade precisa estar contida no horário do evento.",
            )
            mostrar_erro(
                atividade.data_fim,
                "A atividade precisa estar contida no horário do evento.",
            )
            return
        mostrar_erro(atividade.data_inicio, None)

    for campo in campos:
        campo.on_value_change(lambda _: revalidar())
    return revalidar


def coletar_valores(form: EventForm) -> EventFormValues | None:
    """
    Validação de servidor do formulário de evento (a reexecução das regras,
    exibida nos próprios campos). Devolve ``None`` quando inválido.
    """
    # reexecuta as validações por campo (exibem o erro no próprio campo)
    form.nome.validate()
    form.vagas.validate()
    form.valor.validate()

    inicio = _validar_extremo(
        form.data_inicio,
        form.hora_inicio,
        "Informe a data de início.",
        "Informe a hora de início.",
    )
    fim = _validar_extremo(
        form.data_fim,
        form.hora_fim,
        "Informe a data de fim.",
        "Informe a hora de fim.",
    )
    if inicio is not None and fim is not None:
        mostrar_erro(
            form.data_fim,
            "O início do evento precisa ser anterior ao fim."
            if fim <= inicio
            else None,
        )

    lat = form.latitude.value
    lng = form.longitude.value
    erro_lat_lng = (
        "Informe latitude e longitude juntas, ou deixe ambas em branco."
        if (lat is None) != (lng is None)
        else None
    )
    mostrar_erro(form.latitude, erro_lat_lng)
    mostrar_erro(form.longitude, erro_lat_lng)

    campos_com_erro = (
        form.nome,
        form.vagas,
        form.valor,
        form.data_inicio,
        form.hora_inicio,
        form.data_fim,
        form.hora_fim,
        form.latitude,
        form.longitude,
    )
    if any(_campo_com_erro(campo) for campo in campos_com_erro):
        return None

    return EventFormValues(
        nome=(form.nome.value or "").strip(),
        descricao=_vazio_para_none(form.descricao.value),
        data_hora_inicio=inicio,
        data_hora_fim=fim,
        classificacao_indicativa=form.classificacao.value,
        vagas=int(form.vagas.value or 0),
        valor=float(form.valor.value or 0),
        latitude=float(lat) if lat is not None else None,
        longitude=float(lng) if lng is not None else None,
        banner=_vazio_para_none(form.banner.value),
        banner_thumbnail=_vazio_para_none(form.banner_thumbnail.value),
    )


def coletar_atividade(
    form: ActivityForm, evento: EventForm
) -> AtividadeFormValues | None:
    """
    Validação de servidor de uma linha de atividade, exibida nos próprios
    campos (ver ``coletar_valores``). Devolve ``None`` quando inválido.
    """
    form.nome.validate()
    form.sala.validate()
    form.vagas.validate()

    inicio = _validar_extremo(
        form.data_inicio,
        form.hora_inicio,
        "Informe a data de início.",
        "Informe a hora de início.",
    )
    fim = _validar_extremo(
        form.data_fim,
        form.hora_fim,
        "Informe a data de fim.",
        "Informe a hora de fim.",
    )
    if inicio is not None and fim is not None:
        if fim <= inicio:
            mostrar_erro(
                form.data_fim,
                "O início da atividade precisa ser anterior ao fim.",
            )
        else:
            inicio_evento = _ler_data_hora(
                evento.data_inicio.value, evento.hora_inicio.value
            )
            fim_evento = _ler_data_hora(evento.data_fim.value, evento.hora_fim.value)
            if (
                inicio_evento is not None
                and fim_evento is not None
                and (inicio < inicio_evento or fim > fim_evento)
            ):
                mostrar_erro(
                    form.data_inicio,
                    "A atividade precisa estar contida no horário do evento.",
                )
                mostrar_erro(
                    form.data_fim,
                    "A atividade precisa estar contida no horário do evento.",
                )
            else:
                mostrar_erro(form.data_inicio, None)
                mostrar_erro(form.data_fim, None)

    campos_com_erro = (
        form.nome,
        form.sala,
        form.vagas,
        form.data_inicio,
        form.hora_inicio,
        form.data_fim,
        form.hora_fim,
    )
    if any(_campo_com_erro(campo) for campo in campos_com_erro):
        return None

    return AtividadeFormValues(
        nome=(form.nome.value or "").strip(),
        descricao=_vazio_para_none(form.descricao.value),
        sala=(form.sala.value or "").strip(),
        vagas=int(form.vagas.value or 0),
        data_hora_inicio=inicio,
        data_hora_fim=fim,
    )


def mostrar_erro(campo: Any, mensagem: str | None) -> None:
    """
    Exibe (ou limpa) o erro de um campo com a mesma apresentação das
    validações por campo (texto vermelho sob o controle).
    """
    if isinstance(campo, ValidationElement):
        campo.error = mensagem
        return
    campo._props["error"] = mensagem is not None
    campo._props["error-message"] = mensagem or ""


def _campo_com_erro(campo: Any) -> bool:
    """Campo com erro: mensagem definida (ValidationElement) ou prop de erro."""
    if isinstance(campo, ValidationElement):
        return campo.error is not None
    return bool(campo._props.get("error"))


def _validar_extremo(
    campo_data: Any, campo_hora: Any, msg_data: str, msg_hora: str
) -> datetime | None:
    """
    Exige data e hora preenchidas, apontando o erro apenas no(s) subcampo(s)
    vazio(s) — não faz sentido sinalizar o campo que já foi preenchido
    (``date_input``/``time_input`` não aceitam o argumento ``validation``,
    por isso as mensagens vão no par data+hora).
    Devolve o ``datetime`` combinado, ou ``None`` quando o par está
    incompleto/inválido.
    """
    data = (campo_data.value or "").strip()
    hora = (campo_hora.value or "").strip()
    if data:
        mostrar_erro(campo_data, None)
    else:
        mostrar_erro(campo_data, msg_data)
    if hora:
        mostrar_erro(campo_hora, None)
    else:
        mostrar_erro(campo_hora, msg_hora)
    result = _ler_data_hora(data, hora)
    if result is None and data and hora:
        # ambos preenchidos, mas em formato inválido
        mostrar_erro(campo_data, msg_data)
        mostrar_erro(campo_hora, msg_hora)
    return result


def _ler_data_hora(data: str | None, hora: str | None) -> datetime | None:
    """Combina os textos de data (dia/mês/ano) e hora em ``datetime``; ``None`` se inválido."""
    if not data or not hora:
        return None
    try:
        dia = datetime.strptime(data, "%d/%m/%Y").date()
        horario = time.fromisoformat(hora)
    except ValueError:
        return None
    return datetime.combine(dia, horario)


def _vazio_para_none(texto: str | None) -> str | None:
    """Entradas de texto vazias viram ``None`` (colunas anuláveis)."""
    texto = (texto or "").strip()
    return texto or None
