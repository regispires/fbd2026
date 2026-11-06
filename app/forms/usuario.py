"""
Campos e regras compartilhados pelos formulários de usuário (cadastro em
``/user/signup`` e atualização dos dados em ``/user/profile``).
"""

from datetime import date, datetime

from nicegui import ui

from app.forms.validacao import mostrar_erro

TAMANHO_MINIMO_SENHA = 8


def senha_com_tamanho_minimo(senha: str | None) -> bool:
    """Regra de tamanho mínimo para o ``validation`` dos campos de senha."""
    return len(senha or "") >= TAMANHO_MINIMO_SENHA


MENSAGEM_TAMANHO_SENHA = (
    f"A senha precisa ter ao menos {TAMANHO_MINIMO_SENHA} caracteres."
)


def ler_nascimento(campo: ui.date_input) -> date | None:
    """
    Valida a data de nascimento (``date_input`` não aceita ``validation``,
    então o erro é exibido via ``mostrar_erro``); ``None`` se inválida.
    """
    texto = (campo.value or "").strip()
    if not texto:
        mostrar_erro(campo, "Informe a data de nascimento.")
        return None
    try:
        nascimento = datetime.strptime(texto, "%d/%m/%Y").date()
    except ValueError:
        mostrar_erro(campo, "Data inválida (use dia/mês/ano).")
        return None
    if nascimento > date.today():
        mostrar_erro(campo, "A data de nascimento não pode estar no futuro.")
        return None
    mostrar_erro(campo, None)
    return nascimento
