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

from sqlalchemy import text

from app.database import session_maker


def hash_token(token: str) -> str:
    """Hash SHA-256 (hex) do token opaco; só o hash vai ao banco."""
    return hashlib.sha256(token.encode()).hexdigest()


def criar_sessao(usuario_id: int, expira_em: datetime) -> str:
    """
    Cria uma sessão para o usuário e retorna o token opaco a ser enviado ao
    navegador como cookie.

    Sessões expiradas do usuário são removidas antes de criar a nova sessão.
    """
    token = secrets.token_urlsafe(64)
    token_hash = hash_token(token)

    with session_maker() as session:
        session.begin()

        _ = session.execute(
            text(
                "DELETE FROM sessao WHERE id_usuario = :id_usuario AND expira_em <= NOW()"
            ),
            {"id_usuario": usuario_id},
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
                "id_usuario": usuario_id,
                "expira_em": expira_em,
            },
        )

        session.commit()
    return token


def excluir_sessao_por_hash(token_hash: str) -> None:
    """Remove uma sessão pelo hash do token, ignorando inexistência."""
    with session_maker() as session:
        session.begin()

        _ = session.execute(
            text("DELETE FROM sessao WHERE token_hash = :token_hash"),
            {"token_hash": token_hash},
        )

        session.commit()


def obter_id_usuario_por_sessao(token_hash: str) -> int | None:
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
        excluir_sessao_por_hash(token_hash)
        return None

    return row["id_usuario"]
