"""
Página de login.

O formulário usa os inputs do NiceGUI e envia as credenciais como JSON para
``/api/login`` via ``fetch``: o cookie de sessão é definido pelo
``Set-Cookie`` da resposta JSON, então a requisição precisa partir do
navegador (o servidor não pode recebê-la "por procuração"). Em sucesso a
página navega para ``/``; em falha, exibe a mensagem de erro inline.
"""

import json

from fastapi import Request
from nicegui import ui

from app.auth import COOKIE_NAME, cookie_manager
from app.pages.layout import page


# tela dedicada: sem o cabeçalho padrão da aplicação,
# o formulário ocupa toda a altura
@page("/login", with_header=False)
def login_page(request: Request):
    # Se já existe uma sessão válida, não exibir o formulário
    cookie = request.cookies.get(COOKIE_NAME)
    if cookie and cookie_manager.verificar_sessao(cookie):
        ui.navigate.to("/")
        return

    with (
        ui.column()
        .classes("w-full items-center justify-center")
        .style("height: 100vh; margin: 0; padding: 0"),
        ui.card().classes("w-full").style("max-width: 380px"),
    ):
        with ui.row().classes("w-full items-center q-mb-md").style("font-size: 150%"):
            _ = ui.icon("login").classes("text-primary")
            _ = ui.label("Login").style("font-weight: 600")

        _ = (
            ui.label("Faça login para acessar o sistema")
            .classes("text-grey-7")
            .style("text-align: center; margin-bottom: 1rem")
        )

        email = (
            ui.input(
                "E-mail *",
                autocomplete=["username"],
                validation={"Informe o e-mail.": lambda v: bool((v or "").strip())},
            )
            .props("type=email")
            .classes("w-full q-mb-md")
        )
        senha = ui.input(
            "Senha *",
            password=True,
            autocomplete=["current-password"],
            validation={"Informe a senha.": lambda v: bool(v)},
        ).classes("w-full q-mb-md")
        erro = ui.label("E-mail ou senha inválidos").classes("text-negative q-mb-md")
        erro.visible = False
        entrar = ui.button("Entrar").props("filled color=primary").classes("w-full")

        async def enviar() -> None:
            email_valido = email.validate()
            senha_valida = senha.validate()
            if not email_valido or not senha_valida:
                return
            corpo = json.dumps({"email": email.value or "", "senha": senha.value or ""})
            entrar.disable()
            try:
                ok = await ui.run_javascript(
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
                ok = False
            finally:
                entrar.enable()
            if ok:
                ui.navigate.to("/")
            else:
                erro.visible = True

        entrar.on_click(enviar)
