"""
Tratamento centralizado dos erros exibidos ao usuário.

Quando uma página falha (por exemplo, porque o banco de dados está fora do
ar), o NiceGUI monta uma página de erro com a exceção crua. Aqui essa página
é substituída por uma mensagem amigável, sem detalhes internos. O mesmo
tratamento cobre falhas em dependências das páginas — que acontecem antes de
o cliente NiceGUI existir — e nas rotas de API: requisições de páginas
recebem HTML e as de ``/api`` recebem JSON.
"""

import logging
from html import escape
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from nicegui import app as nicegui_app
from nicegui import ui
from sqlalchemy.exc import (
    InterfaceError,
    OperationalError,
)
from sqlalchemy.exc import (
    TimeoutError as SQLAlchemyTimeoutError,
)

logger = logging.getLogger(__name__)

TITULO_GENERICO = "Erro interno do servidor"
MENSAGEM_GENERICA = "Ocorreu um erro inesperado. Tente novamente em alguns instantes."


def pagina_de_erro(_: Exception) -> None:
    """
    Página de erro do NiceGUI, no lugar da página padrão que mostra a
    exceção. Registrada com ``nicegui_app.on_page_exception``.
    """
    ui.page_title(TITULO_GENERICO)
    with (
        ui.column()
        .classes("w-full items-center justify-center")
        .style("min-height: 100vh; padding: 2rem"),
        ui.card().classes("w-full items-center text-center").style("max-width: 480px"),
    ):
        ui.icon("error_outline", size="64px").classes("text-grey-6")
        ui.label(TITULO_GENERICO).classes("text-h5")
        ui.label(MENSAGEM_GENERICA).classes("text-body2 text-grey-7")

        ui.button(
            "Tentar novamente",
            icon="refresh",
            on_click=ui.navigate.reload,
        ).props("color=primary no-caps").classes("q-mt-md")


def _html_de_erro(titulo: str, mensagem: str) -> str:
    """Página HTML simples usada quando o NiceGUI ainda não montou a tela."""
    mensagem_html = f"<p>{escape(mensagem)}</p>" if mensagem else ""
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(titulo)} | FBD 2026</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 2rem;
      background: #f5f5f5;
      color: #212121;
      font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    }}
    main {{
      width: 100%;
      max-width: 480px;
      padding: 2rem;
      border-radius: 0.5rem;
      background: #fff;
      box-shadow: 0 1px 5px rgb(0 0 0 / 20%);
      text-align: center;
    }}
    .icone {{
      width: 4rem;
      height: 4rem;
      margin: 0 auto 1rem;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 50%;
      background: #eeeeee;
      color: #757575;
      font-size: 2rem;
      font-weight: 700;
    }}
    h1 {{ margin: 0 0 0.75rem; font-size: 1.5rem; }}
    p {{ margin: 0 0 1.5rem; color: #616161; line-height: 1.5; }}
    a {{
      display: inline-block;
      padding: 0.5rem 1rem;
      border-radius: 0.25rem;
      background: #1976d2;
      color: #fff;
      text-decoration: none;
      font-weight: 500;
    }}
  </style>
</head>
<body>
  <main>
    <div class="icone">!</div>
    <h1>{escape(titulo)}</h1>
    {mensagem_html}
    <a href="">Tentar novamente</a>
  </main>
</body>
</html>"""


def responder_com_erro(request: Request, exception: Exception) -> Response:
    """
    Resposta para exceções não tratadas nas rotas do FastAPI.

    Rotas de API recebem JSON; as demais (páginas cuja dependência falhou
    antes da criação do cliente NiceGUI) recebem a página HTML amigável.
    """
    logger.error("Erro não tratado em %s", request.url.path, exc_info=exception)
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content={"detail": MENSAGEM_GENERICA},
        )
    return HTMLResponse(
        content=_html_de_erro(TITULO_GENERICO, MENSAGEM_GENERICA),
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
    )


def registrar_tratamento_de_erros(app: FastAPI) -> None:
    """
    Registra a página de erro do NiceGUI e os handlers do FastAPI.

    Deve ser chamado antes de ``ui.run_with``. O handler genérico cobre
    qualquer exceção não tratada; os handlers específicos de conexão
    garantem a mensagem e o status 503 para indisponibilidade do banco.
    """
    nicegui_app.on_page_exception(pagina_de_erro)
    app.add_exception_handler(Exception, responder_com_erro)
