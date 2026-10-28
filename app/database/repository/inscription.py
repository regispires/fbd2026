"""
Dataclasses das inscrições em eventos (``inscricao_evento``) e das presenças
em atividades (``presenca_atividade``).

Módulo separado, sem dependências dos demais módulos de repositório, para
que qualquer um deles importe as classes em nível de módulo sem gerar
ciclo de importação (ex.: ``user.py`` as usa nas anotações de retorno dos
seus getters de inscrições).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import text

from app.database import session_maker
from app.database.repository import eh_pdf, para_bytes
from app.exceptions import (
    AprovacaoPropriaProibida,
    ComprovanteNaoEhPdf,
    InscricaoNaoPendente,
)

Status = Literal["pendente", "confirmada", "cancelada"]


@dataclass
class InscricaoEvento:
    """
    Linha da ``inscricao_evento``.

    O ``valor`` é derivado do preço do evento (cheio ou metade quando
    ``meia=True``); o usuário anexa um ``comprovante_usuario`` (BYTEA);
    o administrador registra um ``comentario_administrador`` após avaliar.
    Os campos extras de exibição são opcionais.
    """

    usuario_id: int
    evento_id: int
    data_inscricao: datetime
    status: str
    valor: float | None = None
    meia: bool = False
    comprovante_usuario: bytes | None = None
    comentario_administrador: str | None = None
    usuario_nome: str | None = None
    evento_nome: str | None = None
    data_hora_inicio: datetime | None = None
    data_hora_fim: datetime | None = None

    @classmethod
    def de_linha(cls, row: Mapping[str, Any]) -> "InscricaoEvento":
        """
        Constrói uma ``InscricaoEvento`` de uma linha; as colunas de exibição
        (nomes, datas do evento) são opcionais e ausentes quando a consulta
        não as seleciona.
        """
        return cls(
            usuario_id=row["id_usuario"],
            evento_id=row["id_evento"],
            data_inscricao=row["data_inscricao"],
            status=row["status"],
            valor=row["valor"],
            meia=row["meia"],
            comprovante_usuario=para_bytes(row["comprovante_usuario"]),
            comentario_administrador=row["comentario_administrador"],
            usuario_nome=row.get("usuario_nome"),
            evento_nome=row.get("evento_nome"),
            data_hora_inicio=row.get("data_hora_inicio"),
            data_hora_fim=row.get("data_hora_fim"),
        )

    def aprovar(self, por_usuario_id: int) -> None:
        """
        Aprova uma inscrição pendente (regra: administrador).

        Levanta ``AprovacaoPropriaProibida`` se o avaliador for o
        próprio solicitante.
        """
        if por_usuario_id == self.usuario_id:
            raise AprovacaoPropriaProibida
        if self.status != "pendente":
            raise InscricaoNaoPendente
        self._definir_status("confirmada")

    def recusar(self, por_usuario_id: int) -> None:
        """
        Recusa (soft cancel) uma inscrição pendente.

        Levanta ``AprovacaoPropriaProibida`` se o avaliador for o
        próprio solicitante.
        """
        if por_usuario_id == self.usuario_id:
            raise AprovacaoPropriaProibida
        if self.status != "pendente":
            raise InscricaoNaoPendente
        self._definir_status("cancelada")

    def cancelar(self) -> None:
        """
        Cancela a inscrição (usuário). Permitido para ``pendente`` ou
        ``confirmada``. O cancelamento é um *soft cancel*.
        """
        self._definir_status("cancelada")

    def atualizar(
        self, meia: bool, valor: float, comprovante_usuario: bytes | None
    ) -> None:
        """
        Edita a meia-entrada, valor derivado e o comprovante de uma
        inscrição **pendente**. Um novo comprovante, quando informado,
        precisa ser PDF.
        """
        if self.status != "pendente":
            raise InscricaoNaoPendente
        if comprovante_usuario is not None and not eh_pdf(comprovante_usuario):
            raise ComprovanteNaoEhPdf
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
                    "user_id": self.usuario_id,
                    "event_id": self.evento_id,
                },
            )
            session.commit()
        self.meia = meia
        self.valor = valor
        self.comprovante_usuario = comprovante_usuario

    def definir_comentario(self, comentario_administrador: str) -> None:
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
                    "user_id": self.usuario_id,
                    "event_id": self.evento_id,
                },
            )
            session.commit()
        self.comentario_administrador = comentario_administrador

    def _definir_status(self, status: Status) -> None:
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
                    "user_id": self.usuario_id,
                    "event_id": self.evento_id,
                },
            )
            session.commit()
        self.status = status


@dataclass
class PresencaAtividade:
    """
    Linha da ``presenca_atividade``, com detalhes para exibição.

    A presença é registrada por um administrador durante ou após a
    atividade; não possui status nem histórico — a linha existe ou não.
    """

    usuario_id: int
    evento_id: int
    id_atividade: int
    evento_nome: str | None = None
    atividade_nome: str | None = None
    sala: str | None = None

    @classmethod
    def de_linha(cls, row: Mapping[str, Any]) -> "PresencaAtividade":
        """Constrói uma ``PresencaAtividade`` de uma linha (com exibição opcional)."""
        return cls(
            usuario_id=row["id_usuario"],
            evento_id=row["id_evento"],
            id_atividade=row["id_atividade"],
            evento_nome=row.get("evento_nome"),
            atividade_nome=row.get("atividade_nome"),
            sala=row.get("sala"),
        )
