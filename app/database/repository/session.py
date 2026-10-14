"""
Operações sobre a tabela sessao (autenticação por cookie de sessão).

O token opaco nunca chega ao banco: apenas o hash SHA-256 do token é
armazenado, de modo que um vazamento do banco não permite assumir as
sessões ativas. Sessões expiradas são removidas no caminho, nas operações
de leitura.
"""

import hashlib
import secrets
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text

from app.database import session_maker


def create_session(user_id: UUID, expires_at: datetime) -> str:
    """
    Cria uma sessão para o usuário e retorna o token opaco a ser enviado ao
    navegador como cookie.

    Sessões expiradas do usuário são removidas antes de criar a nova sessão.
    """
    token = secrets.token_urlsafe(64)
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    with session_maker() as session:
        session.begin()

        _ = session.execute(
            text(
                "DELETE FROM sessao WHERE id_usuario = :id_usuario AND expira_em <= NOW()"
            ),
            {"id_usuario": user_id},
        )
        _ = session.execute(
            text(
                """
                INSERT INTO sessao (token_hash, id_usuario, expira_em)
                VALUES (:token_hash, :id_usuario, :expira_em)
                """
            ),
            {
                "token_hash": token_hash,
                "id_usuario": user_id,
                "expira_em": expires_at,
            },
        )

        session.commit()
    return token


def delete_session_by_hash(token_hash: str) -> None:
    """Remove uma sessão pelo hash do token, ignorando inexistência."""
    with session_maker() as session:
        session.begin()

        _ = session.execute(
            text("DELETE FROM sessao WHERE token_hash = :token_hash"),
            {"token_hash": token_hash},
        )

        session.commit()


def get_user_id_by_session(token_hash: str) -> UUID | None:
    """
    Retorna o ``id_usuario`` da sessão apontada pelo hash do token, ou
    ``None`` se a sessão não existir/estiver expirada. Sessões expiradas são
    removidas no caminho.
    """
    query = text(
        """
        SELECT id_usuario, expira_em
        FROM sessao
        WHERE token_hash = :token_hash
        """
    )
    with session_maker() as session:
        row = session.execute(query, {"token_hash": token_hash}).mappings().first()

    if row is None:
        return None

    if row["expira_em"] <= datetime.now(UTC):
        delete_session_by_hash(token_hash)
        return None

    return row["id_usuario"]
