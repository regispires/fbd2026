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

from app.auth import obter_usuario
from app.database.repository.inscription_list import obter_inscricao
from app.database.repository.user import Usuario


@app.get("/api/registrations/{evento_id}/{usuario_id}/comprovante")
def baixar_comprovante(
    evento_id: int,
    usuario_id: int,
    usuario: Annotated[Usuario, Depends(obter_usuario)],
) -> Response:
    """
    Devolve o comprovante anexado à inscrição como download.

    Acesso restrito ao dono da inscrição ou a administradores; sem
    sessão válida o ``gerenciador_sessao`` redireciona para ``/login``.
    """
    if usuario.id != usuario_id and usuario.papel != "administrador":
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Acesso negado")

    inscricao = obter_inscricao(usuario_id, evento_id)
    if inscricao is None or inscricao.comprovante_usuario is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Comprovante não encontrado"
        )

    return Response(
        content=inscricao.comprovante_usuario,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": (
                f'attachment; filename="comprovante-evento-{evento_id}-usuario-{usuario_id}"'
            )
        },
    )
