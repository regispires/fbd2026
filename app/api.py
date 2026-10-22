"""
Rotas de API de inscrições.

O download do comprovante é a única rota de arquivo da aplicação: o
comprovante fica na coluna BYTEA ``comprovante_usuario`` e só o dono da
inscrição (ou um administrador) pode baixá-lo.
"""

from http import HTTPStatus
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.responses import Response
from nicegui import app

from app.auth import get_current_user
from app.database.repository.inscription_list import get_inscription
from app.database.repository.user import User


@app.get("/api/registrations/{event_id}/{user_id}/comprovante")
def download_comprovante(
    event_id: int,
    user_id: int,
    user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """
    Devolve o comprovante anexado à inscrição como download.

    Acesso restrito ao dono da inscrição ou a administradores; sem
    sessão válida o ``cookie_manager`` redireciona para ``/login``.
    """
    if user.id != user_id and user.papel != "administrador":
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Acesso negado")

    inscription = get_inscription(user_id, event_id)
    if inscription is None or inscription.comprovante_usuario is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Comprovante não encontrado"
        )

    return Response(
        content=inscription.comprovante_usuario,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": (
                f'attachment; filename="comprovante-evento-{event_id}-usuario-{user_id}"'
            )
        },
    )
