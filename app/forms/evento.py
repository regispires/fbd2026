"""
Formulário de evento: context manager com os campos comuns aos dialogs de
criação e edição, as validações que envolvem mais de um campo e a coleta
validada dos valores (``ValoresEvento``, em ``app.modelos``).

O banner e o thumbnail são URLs informadas pelo administrador (não existe
upload de arquivo). Datas e horários usam ``ui.date_input``/``ui.time_input``
(dias em dia/mês/ano e horas em HH:MM) e são combinados em ``datetime`` na coleta.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime

from nicegui import ui

from app.forms.validacao import (
    campo_com_erro,
    campo_data,
    ler_data_hora,
    mostrar_erro,
    obrigatorio,
    validar_extremo,
    vazio_para_none,
)
from app.modelos import ValoresEvento

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


@dataclass
class FormularioEvento:
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


@contextmanager
def formulario_evento(
    valores: ValoresEvento | None = None,
) -> Iterator[FormularioEvento]:
    """
    Renderiza os campos comuns de evento no container atual e devolve as
    referências.

    ``valores`` pré-preenche os campos (edição); ``None`` usa valores
    iniciais neutros (criação).
    """
    v = valores

    with ui.column().classes("w-full gap-2"):
        nome = ui.input(
            "Nome *",
            value=v.nome if v else "",
            validation={"Informe o nome do evento.": obrigatorio},
        ).classes("w-full")
        descricao = ui.textarea(
            "Descrição", value=v.descricao or "" if v else ""
        ).classes("w-full")
        with ui.row().classes("w-full gap-2 items-start"):
            data_inicio = campo_data(
                "Data de início *",
                v.data_hora_inicio.strftime("%d/%m/%Y") if v else "",
            )
            hora_inicio = ui.time_input(
                "Hora de início *",
                value=v.data_hora_inicio.strftime("%H:%M") if v else "",
            ).classes("w-40")

            _ = ui.space()

            data_fim = campo_data(
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
                    "O evento precisa de pelo menos uma vaga.": lambda x: (
                        x is not None and x >= 1
                    )
                },
            ).classes("w-28")
            valor = ui.number(
                "Valor (R$) *",
                min=0,
                value=v.valor if v else 0,
                validation={
                    "Informe o valor (0 para evento gratuito).": lambda x: (
                        x is not None and x >= 0
                    )
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

        formulario = FormularioEvento(
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
        yield formulario


def _validar_datas(
    formulario: FormularioEvento,
) -> tuple[datetime | None, datetime | None]:
    """
    Valida o par data+hora de cada extremidade e a ordem início anterior ao
    fim, exibindo os erros nos campos. Devolve os ``datetime`` combinados.
    """
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
        mostrar_erro(
            formulario.data_fim,
            "O início do evento precisa ser anterior ao fim."
            if fim <= inicio
            else None,
        )
    return inicio, fim


def _validar_lat_lng(formulario: FormularioEvento) -> None:
    """O par latitude/longitude é atômico: ambos preenchidos ou ambos em branco."""
    lat = formulario.latitude.value
    lng = formulario.longitude.value
    erro = (
        "Informe latitude e longitude juntas, ou deixe ambas em branco."
        if (lat is None) != (lng is None)
        else None
    )
    mostrar_erro(formulario.latitude, erro)
    mostrar_erro(formulario.longitude, erro)


def conectar_validacao_evento(formulario: FormularioEvento) -> None:
    """
    Liga as validações do evento que envolvem mais de um campo (data+hora
    de cada extremidade, início anterior ao fim e par latitude/longitude)
    às mudanças dos campos, exibindo os erros como as validações por campo.
    """
    for campo in (
        formulario.data_inicio,
        formulario.hora_inicio,
        formulario.data_fim,
        formulario.hora_fim,
    ):
        campo.on_value_change(lambda _: _validar_datas(formulario))
    formulario.latitude.on_value_change(lambda _: _validar_lat_lng(formulario))
    formulario.longitude.on_value_change(lambda _: _validar_lat_lng(formulario))


def limites_do_formulario(
    formulario: FormularioEvento,
) -> Callable[[], tuple[datetime | None, datetime | None]]:
    """Intervalo do evento lido dos campos do formulário (criação conjunta)."""

    def limites() -> tuple[datetime | None, datetime | None]:
        return (
            ler_data_hora(formulario.data_inicio.value, formulario.hora_inicio.value),
            ler_data_hora(formulario.data_fim.value, formulario.hora_fim.value),
        )

    return limites


def coletar_valores(formulario: FormularioEvento) -> ValoresEvento | None:
    """
    Validação de servidor do formulário de evento (a reexecução das regras,
    exibida nos próprios campos). Devolve ``None`` quando inválido.
    """
    # reexecuta as validações por campo (exibem o erro no próprio campo)
    formulario.nome.validate()
    formulario.vagas.validate()
    formulario.valor.validate()

    inicio, fim = _validar_datas(formulario)
    _validar_lat_lng(formulario)

    campos_com_erro = (
        formulario.nome,
        formulario.vagas,
        formulario.valor,
        formulario.data_inicio,
        formulario.hora_inicio,
        formulario.data_fim,
        formulario.hora_fim,
        formulario.latitude,
        formulario.longitude,
    )
    if any(campo_com_erro(campo) for campo in campos_com_erro):
        return None

    lat = formulario.latitude.value
    lng = formulario.longitude.value
    return ValoresEvento(
        nome=(formulario.nome.value or "").strip(),
        descricao=vazio_para_none(formulario.descricao.value),
        data_hora_inicio=inicio,
        data_hora_fim=fim,
        classificacao_indicativa=formulario.classificacao.value,
        vagas=int(formulario.vagas.value or 0),
        valor=float(formulario.valor.value or 0),
        latitude=float(lat) if lat is not None else None,
        longitude=float(lng) if lng is not None else None,
        banner=vazio_para_none(formulario.banner.value),
        banner_thumbnail=vazio_para_none(formulario.banner_thumbnail.value),
    )
