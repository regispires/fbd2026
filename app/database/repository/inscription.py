"""
Dataclasses das inscrições em eventos (``inscricao_evento``) e das presenças
em atividades (``presenca_atividade``).

Módulo separado, sem dependências dos demais módulos de repositório, para
que qualquer um deles importe as classes em nível de módulo sem gerar
ciclo de importação (ex.: ``user.py`` as usa nas anotações de retorno dos
seus getters de inscrições).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import text

from app.database import session_maker
from app.database.repository import eh_pdf
from app.exceptions import (
    CannotApproveOwnInscription,
    InscriptionNotPending,
    InscriptionProofNotPdf,
)

Status = Literal["pendente", "confirmada", "cancelada"]


@dataclass
class EventInscription:
    """
    Linha da ``inscricao_evento``.

    O ``valor`` é derivado do preço do evento (cheio ou metade quando
    ``meia=True``); o usuário anexa um ``comprovante_usuario`` (BYTEA);
    o administrador registra um ``comentario_administrador`` após avaliar.
    Os campos extras de exibição são opcionais.
    """

    user_id: int
    event_id: int
    data_inscricao: datetime
    status: str
    valor: float | None = None
    meia: bool = False
    comprovante_usuario: bytes | None = None
    comentario_administrador: str | None = None
    user_nome: str | None = None
    event_nome: str | None = None
    data_hora_inicio: datetime | None = None
    data_hora_fim: datetime | None = None

    def approve(self, by_user_id: int) -> None:
        """
        Aprova uma inscrição pendente (regra: administrador).

        Levanta ``CannotApproveOwnInscription`` se o avaliador for o
        próprio solicitante.
        """
        if by_user_id == self.user_id:
            raise CannotApproveOwnInscription
        if self.status != "pendente":
            raise InscriptionNotPending
        self._set_status("confirmada")

    def reject(self, by_user_id: int) -> None:
        """
        Recusa (soft cancel) uma inscrição pendente.

        Levanta ``CannotApproveOwnInscription`` se o avaliador for o
        próprio solicitante.
        """
        if by_user_id == self.user_id:
            raise CannotApproveOwnInscription
        if self.status != "pendente":
            raise InscriptionNotPending
        self._set_status("cancelada")

    def cancel(self) -> None:
        """
        Cancela a inscrição (usuário). Permitido para ``pendente`` ou
        ``confirmada``. O cancelamento é um *soft cancel*.
        """
        self._set_status("cancelada")

    def update(
        self, meia: bool, valor: float, comprovante_usuario: bytes | None
    ) -> None:
        """
        Edita a meia-entrada, valor derivado e o comprovante de uma
        inscrição **pendente**. Um novo comprovante, quando informado,
        precisa ser PDF.
        """
        if self.status != "pendente":
            raise InscriptionNotPending
        if comprovante_usuario is not None and not eh_pdf(comprovante_usuario):
            raise InscriptionProofNotPdf
        query = text(
            """
            UPDATE inscricao_evento
            SET meia = :meia,
                valor = :valor,
                comprovante_usuario = :comprovante_usuario
            WHERE id_usuario = :user_id AND id_evento = :event_id
            """
        )
        with session_maker() as session:
            session.begin()
            _ = session.execute(
                query,
                {
                    "meia": meia,
                    "valor": valor,
                    "comprovante_usuario": comprovante_usuario,
                    "user_id": self.user_id,
                    "event_id": self.event_id,
                },
            )
            session.commit()
        self.meia = meia
        self.valor = valor
        self.comprovante_usuario = comprovante_usuario

    def set_comentario(self, comentario_administrador: str) -> None:
        """Registra o comentário do administrador após avaliar a inscrição."""
        query = text(
            """
            UPDATE inscricao_evento
            SET comentario_administrador = :comentario_administrador
            WHERE id_usuario = :user_id AND id_evento = :event_id
            """
        )
        with session_maker() as session:
            session.begin()
            _ = session.execute(
                query,
                {
                    "comentario_administrador": comentario_administrador,
                    "user_id": self.user_id,
                    "event_id": self.event_id,
                },
            )
            session.commit()
        self.comentario_administrador = comentario_administrador

    def _set_status(self, status: Status) -> None:
        query = text(
            """
            UPDATE inscricao_evento
            SET status = :status
            WHERE id_usuario = :user_id AND id_evento = :event_id
            """
        )
        with session_maker() as session:
            session.begin()
            _ = session.execute(
                query,
                {
                    "status": status,
                    "user_id": self.user_id,
                    "event_id": self.event_id,
                },
            )
            session.commit()
        self.status = status


@dataclass
class ActivityAttendance:
    """
    Linha da ``presenca_atividade``, com detalhes para exibição.

    A presença é registrada por um administrador durante ou após a
    atividade; não possui status nem histórico — a linha existe ou não.
    """

    user_id: int
    event_id: int
    id_atividade: int
    event_nome: str | None = None
    activity_nome: str | None = None
    sala: str | None = None
