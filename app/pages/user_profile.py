"""
Página "Meus dados" (``/user/profile``): o usuário logado atualiza os
próprios dados e troca a senha.

Campos editáveis: nome, e-mail, data de nascimento, sexo e estado civil.
O **CPF** aparece apenas para leitura: é o documento que identifica a
pessoa (único no banco e validado no cadastro), não um dado de perfil. O
papel (tipo de conta) não aparece na página: definir administradores não
cabe ao próprio usuário.

A troca de senha é um formulário separado que exige a senha atual; ao
trocar, as outras sessões do usuário são encerradas (``alterar_senha``).
"""

from typing import Annotated

from fastapi import Depends, Request
from nicegui import ui

from app.auth import NOME_COOKIE, obter_usuario
from app.database.repository.session import hash_token
from app.database.repository.user import (
    ESTADO_CIVIL_ROTULO,
    SEXO_ROTULO,
    Usuario,
)
from app.exceptions import SenhaIncorreta, UsuarioRepetido
from app.forms.usuario import (
    MENSAGEM_TAMANHO_SENHA,
    ler_nascimento,
    senha_com_tamanho_minimo,
)
from app.forms.validacao import campo_data, email_valido, mostrar_erro, obrigatorio
from app.pages.layout import pagina


def _formatar_cpf(cpf: str) -> str:
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


def _dados_pessoais(usuario: Usuario) -> None:
    """Formulário dos dados de perfil, pré-preenchido com os valores atuais."""
    with ui.card().classes("w-full"):
        with ui.row().classes("w-full items-center gap-2"):
            _ = ui.icon("badge", size="24px").classes("text-primary")
            _ = ui.label("Dados pessoais").classes("text-h6")

        nome = ui.input(
            "Nome *",
            value=usuario.nome,
            autocomplete=["name"],
            validation={"Informe o nome.": obrigatorio},
        ).classes("w-full")
        email = (
            ui.input(
                "E-mail *",
                value=usuario.email,
                autocomplete=["email"],
                validation={
                    "Informe o e-mail.": obrigatorio,
                    "E-mail inválido.": email_valido,
                },
            )
            .props("type=email")
            .classes("w-full")
        )
        _ = (
            ui.input("CPF", value=_formatar_cpf(usuario.cpf))
            .props("readonly borderless hint='O CPF não pode ser alterado.'")
            .classes("w-full")
        )
        nascimento = campo_data(
            "Data de nascimento *", usuario.data_nascimento.strftime("%d/%m/%Y")
        ).classes("w-full")
        _ = nascimento.picker.props('default-view="Years"')
        nascimento.on_value_change(lambda: ler_nascimento(nascimento))
        sexo = ui.select(
            SEXO_ROTULO,
            value=usuario.sexo,
            label="Sexo *",
            validation={"Informe o sexo.": obrigatorio},
        ).classes("w-full")
        estado_civil = ui.select(
            ESTADO_CIVIL_ROTULO,
            value=usuario.estado_civil,
            label="Estado civil *",
            validation={"Informe o estado civil.": obrigatorio},
        ).classes("w-full")

        erro = ui.label().classes("text-negative")
        erro.visible = False
        salvar = ui.button("Salvar alterações").props("color=primary").classes("q-mt-sm")

        def enviar() -> None:
            erro.visible = False
            validos = [c.validate() for c in (nome, email, sexo, estado_civil)]
            data_nascimento = ler_nascimento(nascimento)
            if not all(validos) or data_nascimento is None:
                return

            novos = {
                "nome": nome.value.strip(),
                "email": email.value.strip(),
                "data_nascimento": data_nascimento,
                "sexo": sexo.value,
                "estado_civil": estado_civil.value,
            }
            if all(getattr(usuario, campo) == valor for campo, valor in novos.items()):
                ui.notify("Nenhuma alteração para salvar.")
                return

            try:
                # o CPF não é editável: vai o valor atual
                usuario.atualizar(cpf=usuario.cpf, **novos)
            except UsuarioRepetido:
                erro.text = "Esse e-mail já pertence a outro usuário."
                erro.visible = True
                return
            # mantém o objeto em memória igual ao banco para as próximas comparações
            for campo, valor in novos.items():
                setattr(usuario, campo, valor)
            ui.notify("Dados atualizados.", type="positive")

        salvar.on_click(enviar)


def _alterar_senha(usuario: Usuario, sessao_atual: str | None) -> None:
    """Troca de senha: exige a senha atual e a confirmação da nova."""
    with ui.card().classes("w-full"):
        with ui.row().classes("w-full items-center gap-2"):
            _ = ui.icon("lock_reset", size="24px").classes("text-primary")
            _ = ui.label("Alterar senha").classes("text-h6")

        # a validação roda só ao enviar: assim limpar os campos após a troca
        # não exibe os erros de "campo obrigatório"
        atual = (
            ui.input(
                "Senha atual *",
                password=True,
                password_toggle_button=True,
                autocomplete=["current-password"],
                validation={"Informe a senha atual.": obrigatorio},
            )
            .without_auto_validation()
            .classes("w-full")
        )
        nova = (
            ui.input(
                "Nova senha *",
                password=True,
                password_toggle_button=True,
                autocomplete=["new-password"],
                validation={
                    "Informe a nova senha.": obrigatorio,
                    MENSAGEM_TAMANHO_SENHA: senha_com_tamanho_minimo,
                    "A nova senha precisa ser diferente da atual.": (
                        lambda v: v != atual.value
                    ),
                },
            )
            .without_auto_validation()
            .classes("w-full")
        )
        confirmacao = (
            ui.input(
                "Confirmação da nova senha *",
                password=True,
                password_toggle_button=True,
                autocomplete=["new-password"],
                validation={
                    "Confirme a nova senha.": obrigatorio,
                    "As senhas não conferem.": lambda v: v == nova.value,
                },
            )
            .without_auto_validation()
            .classes("w-full")
        )
        _ = ui.label(
            "Ao trocar a senha, você será desconectado dos outros dispositivos."
        ).classes("text-caption text-grey-7")
        trocar = ui.button("Alterar senha").props("color=primary").classes("q-mt-sm")

        def enviar() -> None:
            validos = [c.validate() for c in (atual, nova, confirmacao)]
            if not all(validos):
                return
            try:
                usuario.alterar_senha(atual.value, nova.value, sessao_atual)
            except SenhaIncorreta:
                mostrar_erro(atual, "Senha atual incorreta.")
                return
            for campo in (atual, nova, confirmacao):
                campo.value = ""
                mostrar_erro(campo, None)
            ui.notify("Senha alterada.", type="positive")

        trocar.on_click(enviar)


# página privada: exige sessão válida
@pagina("/user/profile")
def pagina_meus_dados(
    request: Request,
    usuario: Annotated[Usuario, Depends(obter_usuario)],
):
    token = request.cookies.get(NOME_COOKIE)
    sessao_atual = hash_token(token) if token else None

    with ui.column().classes("w-full gap-4").style("max-width: 560px; margin: 0 auto"):
        _ = ui.label("Meus dados").classes("text-h5 q-mt-md")
        _dados_pessoais(usuario)
        _alterar_senha(usuario, sessao_atual)
