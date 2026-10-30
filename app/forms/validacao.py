"""
Regras de validação compartilhadas pelos formulários.

Padronização dos formulários:

- rótulos de campos obrigatórios terminam com ``*``;
- validações de um único campo usam o argumento ``validation`` do próprio
  controle (o NiceGUI mostra o erro imediatamente sob o campo);
- validações que envolvem mais de um campo são ligadas a
  ``on_value_change`` e exibem o erro nos campos da mesma forma (via
  ``mostrar_erro``);
- ``date_input``/``time_input`` não aceitam o argumento ``validation``,
  por isso ``mostrar_erro``/``campo_com_erro`` tratam os dois casos
  (controles com ``validation`` e os demais, via props).
"""

import re
from datetime import datetime, time
from typing import Any

from nicegui import ui
from nicegui.elements.mixins.validation_element import ValidationElement


def obrigatorio(valor: Any) -> bool:
    """Regra de obrigatoriedade para o ``validation`` (aplica ``strip`` em texto)."""
    if isinstance(valor, str):
        return bool(valor.strip())
    return valor is not None


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


def campo_com_erro(campo: Any) -> bool:
    """Campo com erro: mensagem definida (ValidationElement) ou prop de erro."""
    if isinstance(campo, ValidationElement):
        return campo.error is not None
    return bool(campo._props.get("error"))


def somente_digitos(texto: str | None) -> str:
    """Remove a máscara (pontos, traço, espaços) de documentos como o CPF."""
    return "".join(c for c in (texto or "") if c.isdigit())


def cpf_valido(cpf: str | None) -> bool:
    """
    CPF com 11 dígitos e dígitos verificadores corretos. Sequências de um
    único dígito (``111.111.111-11``) passam no cálculo, mas são inválidas.
    """
    digitos = somente_digitos(cpf)
    if len(digitos) != 11 or len(set(digitos)) == 1:
        return False
    for tamanho in (9, 10):
        soma = sum(int(d) * peso for d, peso in zip(digitos, range(tamanho + 1, 1, -1)))
        verificador = (soma * 10) % 11 % 10
        if verificador != int(digitos[tamanho]):
            return False
    return True


def email_valido(email: str | None) -> bool:
    """Formato mínimo de e-mail: ``algo@dominio.tld``, sem espaços."""
    return re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", (email or "").strip()) is not None


def vazio_para_none(texto: str | None) -> str | None:
    """Entradas de texto vazias viram ``None`` (colunas anuláveis)."""
    texto = (texto or "").strip()
    return texto or None


def campo_data(rotulo: str, valor: str = "") -> ui.date_input:
    """Campo de data (dia/mês/ano); o picker emite o mesmo formato do campo."""
    campo = ui.date_input(rotulo, value=valor)
    campo.picker.props('mask="DD/MM/YYYY"')
    return campo


def limitar_calendario(
    campo: ui.date_input,
    inicio_evento: datetime | None,
    fim_evento: datetime | None,
) -> None:
    """
    Restringe o calendário do ``date_input`` ao intervalo do evento (UX do
    picker): ``options`` do QDate — função sobre datas no formato fixo
    ``YYYY/MM/DD`` — e ``navigation-min/max-year-month`` (``YYYY/MM``) para
    travar a navegação para meses fora do evento. Limites ausentes removem
    as restrições (uso temporário enquanto o intervalo do evento não é
    conhecido, no dialog de criação).

    Restrição apenas de interface: a garantia de contenção continua sendo a
    validação inline (``conectar_atividade``) e a checagem do repositório na
    transação da escrita.
    """
    if inicio_evento is None or fim_evento is None:
        _ = campo.picker.props(
            remove=":options navigation-min-year-month navigation-max-year-month"
        )
        return
    _ = campo.picker.props(
        f":options=\"(date) => date >= '{inicio_evento.strftime('%Y/%m/%d')}'"
        f" && date <= '{fim_evento.strftime('%Y/%m/%d')}'\""
    )
    _ = campo.picker.props(
        f'navigation-min-year-month="{inicio_evento.strftime("%Y/%m")}"'
        f' navigation-max-year-month="{fim_evento.strftime("%Y/%m")}"'
    )


def validar_extremo(
    campo_de_data: Any, campo_de_hora: Any, msg_data: str, msg_hora: str
) -> datetime | None:
    """
    Exige data e hora preenchidas, apontando o erro apenas no(s) subcampo(s)
    vazio(s) — não faz sentido sinalizar o campo que já foi preenchido
    (``date_input``/``time_input`` não aceitam o argumento ``validation``,
    por isso as mensagens vão no par data+hora).
    Devolve o ``datetime`` combinado, ou ``None`` quando o par está
    incompleto/inválido.
    """
    data = (campo_de_data.value or "").strip()
    hora = (campo_de_hora.value or "").strip()
    if data:
        mostrar_erro(campo_de_data, None)
    else:
        mostrar_erro(campo_de_data, msg_data)
    if hora:
        mostrar_erro(campo_de_hora, None)
    else:
        mostrar_erro(campo_de_hora, msg_hora)
    result = ler_data_hora(data, hora)
    if result is None and data and hora:
        # ambos preenchidos, mas em formato inválido
        mostrar_erro(campo_de_data, msg_data)
        mostrar_erro(campo_de_hora, msg_hora)
    return result


def ler_data_hora(data: str | None, hora: str | None) -> datetime | None:
    """Combina os textos de data (dia/mês/ano) e hora em ``datetime``; ``None`` se inválido."""
    if not data or not hora:
        return None
    try:
        dia = datetime.strptime(data, "%d/%m/%Y").date()
        horario = time.fromisoformat(hora)
    except ValueError:
        return None
    return datetime.combine(dia, horario)
