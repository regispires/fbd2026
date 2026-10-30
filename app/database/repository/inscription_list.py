"""
Operações sobre inscrições em eventos e presenças em atividades.

Fica separado dos dataclasses (``inscription.py``) e concentrado aqui o que
mistura mais de uma entidade: a inscrição em si (usuário + evento) e a
presença (usuário + evento + atividade).
"""

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.database import session_maker
from app.database.repository import contar_linhas, eh_pdf
from app.database.repository.activity import obter_atividade
from app.database.repository.event import obter_evento
from app.database.repository.inscription import (
    InscricaoEvento,
    PresencaAtividade,
)
from app.database.repository.user import Usuario, obter_usuario_por_id
from app.exceptions import (
    AtividadeDeOutroEvento,
    ComprovanteAusente,
    ComprovanteNaoEhPdf,
    EventoRepetido,
    IdadeAbaixoClassificacao,
    InscricaoNaoConfirmada,
    PresencaNaoEncontrada,
    PresencaRepetida,
    SemVagas,
)


def inscrever_usuario_evento(
    usuario_id: int,
    evento_id: int,
    meia: bool,
    comprovante_usuario: bytes | None,
) -> InscricaoEvento:
    """
    Inscreve um usuário em um evento, aplicando as regras de negócio:

    - o usuário existe e tem idade adequada à classificação indicativa;
    - há vagas disponíveis (inscrições não canceladas contadas);
    - o usuário escolhe meia-entrada (meia=True) ou valor cheio;
    - o valor é derivado do preço do evento;
    - um comprovante PDF deve ser anexado (eventos gratuitos dispensam).

    A inscrição nasce como ``pendente`` e precisa ser confirmada por um
    administrador. O limite de inscrições por par (usuário, evento) é
    garantido pela PK.
    """
    usuario = obter_usuario_por_id(usuario_id)
    evento = obter_evento(evento_id)
    if (
        evento.classificacao_indicativa is not None
        and usuario.idade < evento.classificacao_indicativa
    ):
        raise IdadeAbaixoClassificacao

    if evento.valor > 0 and comprovante_usuario is None:
        # eventos gratuitos não exigem comprovante de pagamento
        raise ComprovanteAusente
    if comprovante_usuario is not None and not eh_pdf(comprovante_usuario):
        raise ComprovanteNaoEhPdf

    usadas = contar_linhas(
        """
        SELECT COUNT(id_usuario) AS total
        FROM inscricao_evento
        WHERE id_evento = :event_id AND status <> 'cancelada'
        """,
        {"event_id": evento_id},
    )
    if usadas >= evento.vagas:
        raise SemVagas

    valor = evento.valor_meia if meia else evento.valor

    with session_maker() as session:
        session.begin()
        try:
            result = session.execute(
                text(
                    """
                    INSERT INTO inscricao_evento
                        (id_usuario, id_evento, valor, meia, comprovante_usuario)
                    VALUES (:user_id, :event_id, :valor, :meia, :comprovante_usuario)
                    RETURNING data_inscricao
                    """
                ),
                {
                    "user_id": usuario_id,
                    "event_id": evento_id,
                    "valor": valor,
                    "meia": meia,
                    "comprovante_usuario": comprovante_usuario,
                },
            )
        except IntegrityError as e:
            raise EventoRepetido from e
        session.commit()
        data_inscricao = result.scalar_one()

    return InscricaoEvento(
        usuario_id=usuario_id,
        evento_id=evento_id,
        data_inscricao=data_inscricao,
        status="pendente",
        valor=valor,
        meia=meia,
        comprovante_usuario=comprovante_usuario,
    )


def registrar_presenca(
    usuario_id: int, evento_id: int, atividade_id: int
) -> PresencaAtividade:
    """
    Registra a presença de um participante em uma atividade (regra de
    negócio: um administrador adiciona a presença durante ou após a
    atividade), aplicando:

    - o usuário existe e a atividade existe (o ``id`` da atividade é único no banco);
    - a atividade pertence ao evento informado (senão,
      ``AtividadeDeOutroEvento``);
    - o usuário está inscrito no evento e a inscrição está **confirmada**
      (senão, ``InscricaoNaoConfirmada``);
    - a atividade ainda tem vagas (contando as presenças registradas).

    O limite de presenças por triplo (usuário, evento, atividade) é
    garantido pela PK: uma presença já existente gera ``IntegrityError``,
    traduzida para ``PresencaRepetida``.
    """
    # Valida a existência do usuário (levanta UsuarioNaoEncontrado se não
    # existir); o resultado não é usado, apenas o efeito de verificação.
    _ = obter_usuario_por_id(usuario_id)
    atividade = obter_atividade(atividade_id)
    if atividade.id_evento != evento_id:
        raise AtividadeDeOutroEvento

    inscricao = _buscar_inscricao_evento(usuario_id, evento_id)
    if inscricao is None or inscricao["status"] != "confirmada":
        raise InscricaoNaoConfirmada

    usadas = contar_linhas(
        """
        SELECT COUNT(id_usuario) AS total
        FROM presenca_atividade
        WHERE id_evento = :event_id
          AND id_atividade = :activity_id
        """,
        {"event_id": evento_id, "activity_id": atividade_id},
    )
    if usadas >= atividade.vagas:
        raise SemVagas

    with session_maker() as session:
        session.begin()
        try:
            session.execute(
                text(
                    """
                    INSERT INTO presenca_atividade
                        (id_usuario, id_evento, id_atividade)
                    VALUES (:user_id, :event_id, :activity_id)
                    """
                ),
                {
                    "user_id": usuario_id,
                    "event_id": evento_id,
                    "activity_id": atividade_id,
                },
            )
        except IntegrityError as e:
            raise PresencaRepetida from e
        session.commit()

    return PresencaAtividade(
        usuario_id=usuario_id,
        evento_id=evento_id,
        id_atividade=atividade_id,
    )


def remover_presenca(usuario_id: int, evento_id: int, atividade_id: int) -> None:
    """
    Remove a presença de um participante da atividade (desfaz um registro
    de presença). Levanta ``PresencaNaoEncontrada`` se não houver presença a
    remover.
    """
    query = text(
        """
        DELETE FROM presenca_atividade
        WHERE id_usuario = :user_id
          AND id_evento = :event_id
          AND id_atividade = :activity_id
        """
    )
    with session_maker() as session:
        session.begin()
        result = session.execute(
            query,
            {
                "user_id": usuario_id,
                "event_id": evento_id,
                "activity_id": atividade_id,
            },
        )
        session.commit()
        removida = result.rowcount == 1
    if not removida:
        raise PresencaNaoEncontrada


def obter_inscricao(usuario_id: int, evento_id: int) -> InscricaoEvento | None:
    """
    Busca a inscrição de um usuário em um evento (qualquer status),
    preenchendo os campos para exibição. ``None`` se não existir.
    """
    row = _buscar_inscricao_evento(usuario_id, evento_id)
    if row is None:
        return None
    return InscricaoEvento.de_linha(row)


def listar_inscricoes_do_evento(evento_id: int) -> list[InscricaoEvento]:
    """Inscrições de um evento, com nomes e datas para o painel administrativo."""
    query = text(
        """
        SELECT i.id_usuario, i.id_evento, i.data_inscricao, i.status,
               i.valor, i.meia, i.comprovante_usuario, i.comentario_administrador,
               u.nome AS usuario_nome,
               e.nome AS evento_nome, e.data_hora_inicio, e.data_hora_fim
        FROM inscricao_evento i
        JOIN usuario u ON u.id = i.id_usuario
        JOIN evento e ON e.id = i.id_evento
        WHERE i.id_evento = :event_id
        ORDER BY i.data_inscricao
        """
    )
    with session_maker() as session:
        rows = session.execute(query, {"event_id": evento_id}).mappings()
        return [InscricaoEvento.de_linha(r) for r in rows]


def listar_participantes(evento_id: int) -> list[Usuario]:
    """
    Usuários com inscrição **confirmada** em um evento — os participantes
    que podem receber presença (regra de negócio do
    ``registrar_presenca``).
    """
    query = text(
        """
        SELECT v.id, v.nome, v.cpf::text, v.email, v.data_nascimento,
               v.papel, v.sexo::text, v.estado_civil::text, v.idade::int
        FROM inscricao_evento i
        JOIN usuario_com_idade v ON v.id = i.id_usuario
        WHERE i.id_evento = :event_id AND i.status = 'confirmada'
        ORDER BY v.nome
        """
    )
    with session_maker() as session:
        rows = session.execute(query, {"event_id": evento_id}).mappings()
        return [Usuario.de_linha(r) for r in rows]


def listar_presencas_atividade(evento_id: int, atividade_id: int) -> list[Usuario]:
    """
    Usuários com presença registrada em uma atividade — para exibir os
    presentes e filtrar quem ainda pode recebê-la (a PK da
    ``presenca_atividade`` garante uma presença por usuário, então a
    interface só oferece os que não estão nesta lista).
    """
    query = text(
        """
        SELECT v.id, v.nome, v.cpf::text, v.email, v.data_nascimento,
               v.papel, v.sexo::text, v.estado_civil::text, v.idade::int
        FROM presenca_atividade p
        JOIN usuario_com_idade v ON v.id = p.id_usuario
        WHERE p.id_evento = :event_id AND p.id_atividade = :activity_id
        ORDER BY v.nome
        """
    )
    with session_maker() as session:
        rows = session.execute(
            query, {"event_id": evento_id, "activity_id": atividade_id}
        ).mappings()
        return [Usuario.de_linha(r) for r in rows]


# --- Helpers internos -------------------------------------------------------


def _buscar_inscricao_evento(usuario_id: int, evento_id: int) -> dict | None:
    query = text(
        """
        SELECT i.id_usuario, i.id_evento, i.data_inscricao, i.status, i.valor,
               i.meia, i.comprovante_usuario, i.comentario_administrador,
               u.nome AS usuario_nome
        FROM inscricao_evento i
        JOIN usuario u ON u.id = i.id_usuario
        WHERE i.id_usuario = :user_id AND i.id_evento = :event_id
        LIMIT 1
        """
    )
    with session_maker() as session:
        row = (
            session.execute(query, {"user_id": usuario_id, "event_id": evento_id})
            .mappings()
            .first()
        )
    return dict(row) if row is not None else None
