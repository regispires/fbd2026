"""
Página de cadastro de usuário (``/user/signup``).

O usuário é criado no servidor (``criar_usuario``, senha com hash argon2id)
e todo cadastro recebe o papel de associado. Em seguida, a página faz o
login com as mesmas credenciais pelo ``fetch`` para ``/api/login`` (o
cookie de sessão precisa ser definido por uma resposta recebida pelo
navegador, como na página de login) e navega para ``/``.
"""

import json
from datetime import date, datetime

from fastapi import Request
from nicegui import ui

from app.auth import NOME_COOKIE, gerenciador_sessao
from app.database.repository.user import (
    ESTADO_CIVIL_ROTULO,
    SEXO_ROTULO,
    criar_usuario,
)
from app.exceptions import UsuarioRepetido
from app.forms.validacao import (
    campo_data,
    cpf_valido,
    email_valido,
    mostrar_erro,
    obrigatorio,
    somente_digitos,
)
from app.pages.layout import pagina

TAMANHO_MINIMO_SENHA = 8


def _ler_nascimento(campo: ui.date_input) -> date | None:
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


# tela dedicada, como a de login: sem o cabeçalho padrão da aplicação
@pagina("/user/signup", com_cabecalho=False)
def pagina_cadastro(request: Request):
    # quem já está autenticado não precisa de um novo cadastro
    cookie = request.cookies.get(NOME_COOKIE)
    if cookie and gerenciador_sessao.verificar_sessao(cookie):
        ui.navigate.to("/")
        return

    with (
        ui.column()
        .classes("w-full items-center justify-center")
        .style("min-height: 100vh; margin: 0; padding: 1rem 0"),
        ui.card().classes("w-full").style("max-width: 420px"),
    ):
        with ui.row().classes("w-full items-center q-mb-md").style("font-size: 150%"):
            _ = ui.icon("person_add").classes("text-primary")
            _ = ui.label("Cadastro").style("font-weight: 600")

        nome = ui.input(
            "Nome *",
            autocomplete=["name"],
            validation={"Informe o nome.": obrigatorio},
        ).classes("w-full")
        cpf = (
            ui.input(
                "CPF *",
                validation={
                    "Informe o CPF.": obrigatorio,
                    "CPF inválido.": cpf_valido,
                },
            )
            # a máscara só formata a exibição; o valor guarda apenas os dígitos
            .props('mask="###.###.###-##" unmasked-value inputmode=numeric')
            .classes("w-full")
        )
        email = (
            ui.input(
                "E-mail *",
                autocomplete=["email"],
                validation={
                    "Informe o e-mail.": obrigatorio,
                    "E-mail inválido.": email_valido,
                },
            )
            .props("type=email")
            .classes("w-full")
        )
        nascimento = campo_data("Data de nascimento *").classes("w-full")
        # o calendário abre na escolha do ano, mais prático para datas antigas
        _ = nascimento.picker.props('default-view="Years"')
        nascimento.on_value_change(lambda: _ler_nascimento(nascimento))
        sexo = ui.select(
            SEXO_ROTULO,
            label="Sexo *",
            validation={"Informe o sexo.": obrigatorio},
        ).classes("w-full")
        estado_civil = ui.select(
            ESTADO_CIVIL_ROTULO,
            label="Estado civil *",
            validation={"Informe o estado civil.": obrigatorio},
        ).classes("w-full")

        senha = ui.input(
            "Senha *",
            password=True,
            password_toggle_button=True,
            autocomplete=["new-password"],
            validation={
                "Informe a senha.": obrigatorio,
                f"A senha precisa ter ao menos {TAMANHO_MINIMO_SENHA} caracteres.": (
                    lambda v: len(v or "") >= TAMANHO_MINIMO_SENHA
                ),
            },
        ).classes("w-full")
        confirmacao = ui.input(
            "Confirmação da senha *",
            password=True,
            password_toggle_button=True,
            autocomplete=["new-password"],
            validation={
                "Confirme a senha.": obrigatorio,
                "As senhas não conferem.": lambda v: v == senha.value,
            },
        ).classes("w-full")
        # a confirmação depende da senha: revalidar quando a senha muda
        senha.on_value_change(lambda: confirmacao.value and confirmacao.validate())

        erro = ui.label().classes("text-negative")
        erro.visible = False
        cadastrar = (
            ui.button("Cadastrar").props("filled color=primary").classes("w-full q-mt-md")
        )
        with ui.row().classes("w-full justify-center items-center gap-1 q-mt-sm"):
            _ = ui.label("Já tem uma conta?").classes("text-grey-7")
            _ = ui.link("Entrar", "/login")

        async def enviar() -> None:
            erro.visible = False
            # todos os campos são validados (sem curto-circuito) para que os
            # erros apareçam de uma vez
            validos = [
                campo.validate()
                for campo in (nome, cpf, email, sexo, estado_civil, senha, confirmacao)
            ]
            data_nascimento = _ler_nascimento(nascimento)
            if not all(validos) or data_nascimento is None:
                return

            email_informado = email.value.strip()
            cadastrar.disable()
            try:
                try:
                    _ = criar_usuario(
                        nome=nome.value.strip(),
                        cpf=somente_digitos(cpf.value),
                        email=email_informado,
                        senha=senha.value,
                        data_nascimento=data_nascimento,
                        sexo=sexo.value,
                        estado_civil=estado_civil.value,
                    )
                except UsuarioRepetido:
                    erro.text = "Já existe um usuário com esse CPF ou e-mail."
                    erro.visible = True
                    return

                corpo = json.dumps({"email": email_informado, "senha": senha.value})
                try:
                    logado = await ui.run_javascript(
                        f"""
                        fetch('/api/login', {{
                            method: 'POST',
                            headers: {{'Content-Type': 'application/json'}},
                            body: JSON.stringify({corpo}),
                        }}).then((r) => r.ok)
                        """,
                        timeout=10,
                    )
                except TimeoutError:
                    logado = False
            finally:
                cadastrar.enable()

            if logado:
                ui.navigate.to("/")
            else:
                # o cadastro foi feito; só o login automático falhou
                ui.notify("Cadastro realizado. Faça login para continuar.", type="positive")
                ui.navigate.to("/login")

        cadastrar.on_click(enviar)
