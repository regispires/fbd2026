"""
Operações sobre inscrições em eventos e presenças em atividades.
"""

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.database import session_maker
from app.database.repository import as_bytes
from app.database.repository.activity import get_activity
from app.database.repository.event import get_event
from app.database.repository.inscription import (
    ActivityAttendance,
    EventInscription,
)
from app.database.repository.user import User, get_user
from app.exceptions import (
    AgeBelowClassification,
    AttendanceNotFound,
    DuplicateAttendance,
    DuplicateEventRegistration,
    EventInscriptionNotConfirmed,
    NoMoreVacancy,
    WrongEventActivityInscription,
)


@dataclass
class InscriptionList:
    """Inscrições de um evento, para o painel administrativo."""

    items: list[EventInscription]
    on_change: Callable
    event_id: int

    def reload(self) -> None:
        query = text(
            """
            SELECT i.id_usuario, i.id_evento, i.data_inscricao, i.status,
                   i.valor, i.comprovante_usuario, i.comentario_administrador,
                   u.nome AS user_nome,
                   e.nome AS event_nome, e.data_hora_inicio, e.data_hora_fim
            FROM inscricao_evento i
            JOIN usuario u ON u.id = i.id_usuario
            JOIN evento e ON e.id = i.id_evento
            WHERE i.id_evento = :event_id
            ORDER BY i.data_inscricao
            """
        )
        with session_maker() as session:
            rows = session.execute(query, {"event_id": self.event_id}).mappings()
        self.items = [
            EventInscription(
                user_id=r["id_usuario"],
                event_id=r["id_evento"],
                data_inscricao=r["data_inscricao"],
                status=r["status"],
                valor=r["valor"],
                comprovante_usuario=as_bytes(r["comprovante_usuario"]),
                comentario_administrador=r["comentario_administrador"],
                user_nome=r["user_nome"],
                event_nome=r["event_nome"],
                data_hora_inicio=r["data_hora_inicio"],
                data_hora_fim=r["data_hora_fim"],
            )
            for r in rows
        ]
        self.on_change()


def register_user_for_event(
    user_id: UUID,
    event_id: int,
    valor: float,
    comprovante_usuario: bytes | None,
) -> EventInscription:
    """
    Inscreve um usuário em um evento, aplicando as regras de negócio:

    - o usuário existe e tem idade adequada à classificação indicativa;
    - há vagas disponíveis (inscrições não canceladas contadas);
    - o usuário informa o valor da inscrição e anexa um comprovante.

    A inscrição nasce como ``pendente`` e precisa ser confirmada por um
    administrador (regra de negócio). O limite de inscrições por par
    (usuário, evento) é garantido pela PK: uma nova inscrição no mesmo par
    gera ``IntegrityError``, traduzido para ``DuplicateEventRegistration``.
    """
    user = get_user(user_id)
    event = get_event(event_id)
    if (
        event.classificacao_indicativa is not None
        and user.idade < event.classificacao_indicativa
    ):
        raise AgeBelowClassification

    used = _count_active(
        """
        SELECT COUNT(id_usuario) AS total
        FROM inscricao_evento
        WHERE id_evento = :event_id AND status <> 'cancelada'
        """,
        {"event_id": event_id},
    )
    if used >= event.vagas:
        raise NoMoreVacancy

    with session_maker() as session:
        session.begin()
        try:
            result = session.execute(
                text(
                    """
                    INSERT INTO inscricao_evento
                        (id_usuario, id_evento, valor, comprovante_usuario)
                    VALUES (:user_id, :event_id, :valor, :comprovante_usuario)
                    RETURNING data_inscricao
                    """
                ),
                {
                    "user_id": user_id,
                    "event_id": event_id,
                    "valor": valor,
                    "comprovante_usuario": comprovante_usuario,
                },
            )
        except IntegrityError as e:
            raise DuplicateEventRegistration from e
        session.commit()
        data_inscricao = result.scalar_one()

    return EventInscription(
        user_id=user_id,
        event_id=event_id,
        data_inscricao=data_inscricao,
        status="pendente",
        valor=valor,
        comprovante_usuario=comprovante_usuario,
    )


def add_attendance(
    user_id: UUID, event_id: int, numero_atividade: int
) -> ActivityAttendance:
    """
    Registra a presença de um participante em uma atividade (regra de
    negócio: um administrador adiciona a presença durante ou após a
    atividade), aplicando:

    - o usuário existe e a atividade existe (``numero`` é único no banco);
    - a atividade pertence ao evento informado (senão,
      ``WrongEventActivityInscription``);
    - o usuário está inscrito no evento e a inscrição está **confirmada**
      (senão, ``EventInscriptionNotConfirmed``);
    - a atividade ainda tem vagas (contando as presenças registradas).

    O limite de presenças por triplo (usuário, evento, atividade) é
    garantido pela PK: uma presença já existente gera ``IntegrityError``,
    traduzida para ``DuplicateAttendance``.
    """
    # Valida a existência do usuário (levanta UserNotFound se não existir);
    # o resultado não é usado, apenas o efeito de verificação.
    _ = get_user(user_id)
    activity = get_activity(numero_atividade)
    if activity.id_evento != event_id:
        raise WrongEventActivityInscription

    insp = _fetch_event_inscription(user_id, event_id)
    if insp is None:
        raise EventInscriptionNotConfirmed
    if insp["status"] != "confirmada":
        raise EventInscriptionNotConfirmed

    used = _count_active(
        """
        SELECT COUNT(id_usuario) AS total
        FROM presenca_atividade
        WHERE id_evento = :event_id
          AND numero_atividade = :numero_atividade
        """,
        {"event_id": event_id, "numero_atividade": numero_atividade},
    )
    if used >= activity.vagas:
        raise NoMoreVacancy

    with session_maker() as session:
        session.begin()
        try:
            session.execute(
                text(
                    """
                    INSERT INTO presenca_atividade
                        (id_usuario, id_evento, numero_atividade)
                    VALUES (:user_id, :event_id, :numero_atividade)
                    """
                ),
                {
                    "user_id": user_id,
                    "event_id": event_id,
                    "numero_atividade": numero_atividade,
                },
            )
        except IntegrityError as e:
            raise DuplicateAttendance from e
        session.commit()

    return ActivityAttendance(
        user_id=user_id,
        event_id=event_id,
        numero_atividade=numero_atividade,
    )


def remove_attendance(user_id: UUID, event_id: int, numero_atividade: int) -> None:
    """
    Remove a presença de um participante da atividade (desfaz um registro
    de presença). Levanta ``AttendanceNotFound`` se não houver presença a
    remover.
    """
    query = text(
        """
        DELETE FROM presenca_atividade
        WHERE id_usuario = :user_id
          AND id_evento = :event_id
          AND numero_atividade = :numero_atividade
        """
    )
    with session_maker() as session:
        session.begin()
        result = session.execute(
            query,
            {
                "user_id": user_id,
                "event_id": event_id,
                "numero_atividade": numero_atividade,
            },
        )
        session.commit()
        removed = result.rowcount == 1
    if not removed:
        raise AttendanceNotFound


def get_event_inscriptions(event_id: int) -> list[EventInscription]:
    """Inscrições em um evento, com nome do usuário para exibição."""
    query = text(
        """
        SELECT i.id_usuario, i.id_evento, i.data_inscricao, i.status,
               i.valor, i.comprovante_usuario, i.comentario_administrador,
               u.nome AS user_nome
        FROM inscricao_evento i
        JOIN usuario u ON u.id = i.id_usuario
        WHERE i.id_evento = :event_id
        ORDER BY i.data_inscricao
        """
    )
    with session_maker() as session:
        rows = session.execute(query, {"event_id": event_id}).mappings()
    return [
        EventInscription(
            user_id=r["id_usuario"],
            event_id=r["id_evento"],
            data_inscricao=r["data_inscricao"],
            status=r["status"],
            valor=r["valor"],
            comprovante_usuario=as_bytes(r["comprovante_usuario"]),
            comentario_administrador=r["comentario_administrador"],
            user_nome=r["user_nome"],
        )
        for r in rows
    ]


def get_participants(event_id: int) -> list[User]:
    """
    Usuários com inscrição **confirmada** em um evento — os participantes
    que podem receber presença (regra de negócio da ``add_attendance``).
    """
    query = text(
        """
        SELECT u.id, u.nome, u.cpf::text, u.email, u.data_nascimento, u.papel,
               v.idade::int
        FROM inscricao_evento i
        JOIN usuario u ON u.id = i.id_usuario
        JOIN usuario_com_idade v ON v.id = u.id
        WHERE i.id_evento = :event_id AND i.status = 'confirmada'
        ORDER BY u.nome
        """
    )
    with session_maker() as session:
        rows = session.execute(query, {"event_id": event_id}).mappings()
    return [
        User(
            id=r["id"],
            nome=r["nome"],
            cpf=r["cpf"],
            email=r["email"],
            data_nascimento=r["data_nascimento"],
            papel=r["papel"],
            idade=r["idade"],
        )
        for r in rows
    ]


# --- Helpers internos -------------------------------------------------------


def _fetch_event_inscription(user_id: UUID, event_id: int) -> dict | None:
    query = text(
        """
        SELECT id_usuario, id_evento, data_inscricao, status, valor,
               comprovante_usuario, comentario_administrador
        FROM inscricao_evento
        WHERE id_usuario = :user_id AND id_evento = :event_id
        LIMIT 1
        """
    )
    with session_maker() as session:
        row = (
            session.execute(query, {"user_id": user_id, "event_id": event_id})
            .mappings()
            .first()
        )
    return dict(row) if row is not None else None


def _count_active(query: str, params: dict) -> int:
    """Contagem de inscrições ativas (não canceladas) em coluna explícita."""
    with session_maker() as session:
        row = session.execute(text(query), params).mappings().first()
    return int(row["total"]) if row else 0
