"""
Autenticação por cookie de sessão.

O fluxo é o seguinte:

1. O usuário envia o e-mail e a senha para ``POST /api/login``;
2. As credenciais são validadas (``autenticar_usuario``, senha com hash
   argon2id) e, se válidas, é criada uma linha em ``sessao`` contendo o
   **hash SHA-256** de um token opaco gerado com o módulo ``secrets``;
3. O token em si nunca vai ao banco: ele é enviado ao navegador apenas como
   cookie ``HttpOnly``/``SameSite=Strict``, de modo que um vazamento do banco
   de dados não permite assumir as sessões ativas;
4. Páginas privadas declaram ``Depends(gerenciador_sessao)`` (via
   ``app.pages.layout.pagina``, que repassa kwargs para o FastAPI): sem
   sessão válida o navegador recebe um redirect HTTPStatus.SEE_OTHER para
   ``/login``.

Este módulo atua como controller da API de autenticação: valida o cookie
(``GerenciadorDeSessao``) e implementa as rotas ``/api/login`` e
``/api/logout``. Todas as operações de banco sobre a tabela ``sessao``
ficam em ``app.database.repository.session``.
"""

from datetime import UTC, datetime
from http import HTTPStatus
from typing import Annotated, override

from fastapi import Depends, HTTPException
from fastapi.params import Cookie
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import APIKeyCookie
from nicegui import app
from pydantic import BaseModel

from app.database.repository import garantir_timezone
from app.database.repository.session import (
    criar_sessao,
    excluir_sessao_por_hash,
    hash_token,
    obter_id_usuario_por_sessao,
)
from app.database.repository.user import (
    Usuario,
    autenticar_usuario,
    obter_usuario_por_id,
)
from app.database.settings import settings

NOME_COOKIE = "session_cookie"


class GerenciadorDeSessao(APIKeyCookie):
    """
    Scheme de segurança do cookie de sessão.

    ``check_api_key`` — o hook que ``APIKeyCookie.__call__`` invoca quando o
    scheme é usado como dependency — é o guarda de autenticação: com
    ``auto_error=True``, cookie ausente **ou inválido** levanta o erro de
    "não autenticado" (o mecanismo de dependências do FastAPI só rejeita a
    request por exceção, então a validação negativa precisa levantar, não
    apenas retornar ``None``). A verificação em si fica em
    ``verificar_sessao``, que também serve aos consumidores sem dependência
    (``obter_usuario`` e a página de login).
    """

    def __init__(self) -> None:
        super().__init__(name=NOME_COOKIE, auto_error=True)

    def verificar_sessao(self, token: str | None) -> bool:
        """
        Verifica no banco se o token pertence a uma sessão válida
        (existe e não expirou). Sessões expiradas são removidas no caminho.
        """
        if not token:
            return False

        return obter_id_usuario_por_sessao(hash_token(token)) is not None

    @override
    def check_api_key(self, api_key: str | None) -> str | None:
        if not api_key or not self.verificar_sessao(api_key):
            if self.auto_error:
                raise self.make_not_authenticated_error()
            return None
        return api_key

    @override
    def make_not_authenticated_error(self) -> HTTPException:
        """
        Cookie ausente vira redirect HTTPStatus.SEE_OTHER para ``/login`` em vez do 401
        padrão: o consumidor principal das páginas é o navegador, que deve
        cair direto no formulário de login. Rotas de API usam
        ``obter_usuario``, que levanta 401.
        """
        return HTTPException(
            status_code=HTTPStatus.SEE_OTHER, headers={"Location": "/login"}
        )


gerenciador_sessao = GerenciadorDeSessao()


def eh_administrador(usuario: Usuario | None) -> bool:
    """``True`` quando o usuário está autenticado e tem papel de administrador."""
    return usuario is not None and usuario.papel == "administrador"


def obter_usuario_opcional(
    token: Annotated[str | None, Cookie(alias=NOME_COOKIE)] = None,
) -> Usuario | None:
    """
    Retorna o usuário autenticado **se** existir uma sessão válida;
    ``None`` caso contrário. Útil para páginas públicas que precisam
    saber o usuário logado para condicionar a interface.

    O token vem do ``Cookie``, resolvido pelo FastAPI a cada requisição,
    então a função pode ser usada como dependência
    (``Annotated[Usuario | None, Depends(obter_usuario_opcional)]``).
    """
    if not token or not gerenciador_sessao.verificar_sessao(token):
        return None
    usuario_id = obter_id_usuario_por_sessao(hash_token(token))
    if usuario_id is None:
        return None
    return obter_usuario_por_id(usuario_id)


def obter_usuario(token: Annotated[str, Depends(gerenciador_sessao)]) -> Usuario:
    """
    Retorna o usuário autenticado ou levanta 401 se a sessão não
    existir/estiver expirada.
    """
    usuario_id = obter_id_usuario_por_sessao(hash_token(token))
    if usuario_id is None:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED, detail="Sessão inválida ou expirada"
        )
    return obter_usuario_por_id(usuario_id)


def exigir_administrador(
    usuario: Annotated[Usuario, Depends(obter_usuario)],
) -> None:
    """Dependência de papel: restringe a rota a usuários ``administrador``."""
    if usuario.papel != "administrador":
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Requer papel de administrador"
        )


class RequisicaoLogin(BaseModel):
    """Credenciais enviadas pela página de login em JSON."""

    email: str
    senha: str


@app.post("/api/login", response_model=None)
def login(payload: RequisicaoLogin) -> JSONResponse:
    """
    Valida as credenciais enviadas em JSON, cria a sessão e define o cookie.

    A navegação não é feita pela resposta: em sucesso a página de login
    navega para "/" após receber o 200; em falha, responde 401 e a página
    exibe a mensagem de erro inline.
    """

    usuario = autenticar_usuario(payload.email, payload.senha)
    if usuario is None:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED, detail="E-mail ou senha inválidos"
        )

    expira_em = garantir_timezone(datetime.now(UTC) + settings.SESSION_DURATION_HOURS)
    token = criar_sessao(usuario.id, expira_em)
    response = JSONResponse(content={"status": "ok"})

    response.set_cookie(
        key=NOME_COOKIE,
        value=token,
        httponly=True,
        samesite="strict",
        # habilitando token seguro apenas em produção
        secure=settings.ENVIRONMENT == "PRODUCTION",
        max_age=int(settings.SESSION_DURATION_HOURS.total_seconds()),
    )

    return response


@app.post("/api/logout", response_model=None)
def logout(token: Annotated[str | None, Cookie(alias=NOME_COOKIE)]) -> RedirectResponse:
    """Remove a sessão do banco e limpa o cookie, redirecionando para ``/login``."""
    response = RedirectResponse(url="/login", status_code=HTTPStatus.SEE_OTHER)
    if token:
        excluir_sessao_por_hash(hash_token(token))
        response.delete_cookie(key=NOME_COOKIE)
    return response
