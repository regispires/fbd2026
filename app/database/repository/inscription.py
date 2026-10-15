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
from app.exceptions import InscriptionNotPending

Status = Literal["pendente", "confirmada", "cancelada"]


@dataclass
class EventInscription:
    """
    Linha da ``inscricao_evento``.

    O usuário informa o ``valor`` da inscrição e anexa um
    ``comprovante_usuario`` (BYTEA); o administrador registra uma
    ``comentario_administrador`` após avaliar. Os campos extras de exibição
    (nome do usuário/evento, horários) são opcionais: cada leitura preenche
    apenas as colunas que o contexto da interface precisa.
    """

    user_id: int
    event_id: int
    data_inscricao: datetime
    status: str
    valor: float | None = None
    comprovante_usuario: bytes | None = None
    comentario_administrador: str | None = None
    user_nome: str | None = None
    event_nome: str | None = None
    data_hora_inicio: datetime | None = None
    data_hora_fim: datetime | None = None

    def confirm(self) -> None:
        """
        Confirma uma inscrição pendente (regra de negócio: a confirmação é
        feita por um administrador).

        O limite de vagas não é revalidado aqui: a vaga já foi consumida no
        momento da inscrição (que nasce ``pendente``), e a confirmação só
        troca o status mantendo a inscrição ativa.
        """
        self._set_status("confirmada")

    def cancel(self) -> None:
        """
        Cancela a inscrição de evento (regra de negócio: o usuário que
        solicitou a inscrição pode cancelá-la, pendente ou confirmada).

        O cancelamento é um *soft cancel* (``status = 'cancelada'``), de
        modo a preservar o histórico. A recusa do administrador também usa
        este mesmo status (o enum ``status_inscricao`` não possui
        ``recusada``).
        """
        self._set_status("cancelada")

    def update(self, valor: float, comprovante_usuario: bytes | None) -> None:
        """
        Edita o valor e o comprovante de uma inscrição pendente (regra de
        negócio: o usuário só pode editar enquanto a inscrição é
        ``pendente``).
        """
        if self.status != "pendente":
            raise InscriptionNotPending
        query = text(
            """
            UPDATE inscricao_evento
            SET valor = :valor, comprovante_usuario = :comprovante_usuario
            WHERE id_usuario = :user_id AND id_evento = :event_id
            """
        )
        with session_maker() as session:
            session.begin()
            _ = session.execute(
                query,
                {
                    "valor": valor,
                    "comprovante_usuario": comprovante_usuario,
                    "user_id": self.user_id,
                    "event_id": self.event_id,
                },
            )
            session.commit()
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
    numero_atividade: int
    event_nome: str | None = None
    activity_nome: str | None = None
    sala: str | None = None
