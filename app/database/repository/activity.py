"""
Operações sobre atividades e os ministrantes.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import session_maker
from app.database.repository import ensure_timezone
from app.database.repository.user import User
from app.exceptions import (
    ActivityHasDependencies,
    ActivityNotFound,
    ActivityWithoutLecturer,
    DuplicateLecturer,
    EventNotFound,
    InvalidActivitySchedule,
)


def _ensure_inside_event(
    session: Session,
    event_id: int,
    data_hora_inicio: datetime,
    data_hora_fim: datetime,
) -> None:
    """
    A atividade precisa estar contida no intervalo do evento.

    Executa a leitura no ``session`` já aberto pelo chamador, para que
    validação e escrita aconteçam na mesma transação.
    """
    query = text(
        """
        SELECT data_hora_inicio, data_hora_fim
        FROM evento
        WHERE id = :id_evento
        LIMIT 1
        """
    )
    row = session.execute(query, {"id_evento": event_id}).mappings().first()
    if row is None:
        raise EventNotFound
    # o banco devolve datetimes com timezone; a entrada é normalizada para
    # que a comparação não misture datetimes com e sem timezone
    if (
        ensure_timezone(data_hora_inicio) < row["data_hora_inicio"]
        or ensure_timezone(data_hora_fim) > row["data_hora_fim"]
    ):
        raise InvalidActivitySchedule


@dataclass
class Lecturer:
    """Linha da ``ministra_atividade`` com os dados do usuário para exibição."""

    id_usuario: int
    id_evento: int
    id_atividade: int
    mini_bio: str | None
    instituicao: str
    link_lattes: str | None
    user: User


@dataclass
class LecturerInput:
    """
    Entrada para ``Activity.add_lecturers``.

    Espelha a nulabilidade da ``ministra_atividade``: ``instituicao`` é
    obrigatório, ``mini_bio`` e ``link_lattes`` são opcionais.
    """

    user: User
    mini_bio: str | None
    instituicao: str
    link_lattes: str | None


@dataclass
class ActivityInput:
    """
    Entrada para criação de atividades junto com o evento (``create_event``).

    Espelha as colunas de ``atividade`` sem as chaves (``id`` é gerado pelo
    banco e ``id_evento`` é o do evento criado); a validação de que o horário
    está contido no do evento é feita no ``create_event``. A regra de negócio
    exige ao menos um ministrante por atividade.
    """

    nome: str
    descricao: str | None
    sala: str
    vagas: int
    data_hora_inicio: datetime
    data_hora_fim: datetime
    lecturers: list[LecturerInput] = field(default_factory=list)


@dataclass
class ActivityPreview:
    """Campos resumidos da atividade, para exibição em listas."""

    id_evento: int
    id: int
    nome: str
    sala: str
    data_hora_inicio: datetime
    data_hora_fim: datetime
    vagas: int


@dataclass
class Activity(ActivityPreview):
    """Atividade completa, incluindo a descrição e os ministrantes."""

    lecturers: list[Lecturer]
    descricao: str | None

    def update(
        self,
        nome: str,
        descricao: str | None,
        sala: str,
        vagas: int,
        data_hora_inicio: datetime,
        data_hora_fim: datetime,
    ) -> None:
        """
        Atualiza os dados da atividade, validando o intervalo do evento na
        mesma transação da escrita.
        """
        query = text(
            """
            UPDATE atividade
            SET nome = :nome, descricao = :descricao, sala = :sala, vagas = :vagas,
                data_hora_inicio = :data_hora_inicio, data_hora_fim = :data_hora_fim
            WHERE id = :id AND id_evento = :id_evento
            """
        )
        with session_maker() as session:
            session.begin()
            self._ensure_inside_event(session, data_hora_inicio, data_hora_fim)
            _ = session.execute(
                query,
                {
                    "id": self.id,
                    "id_evento": self.id_evento,
                    "nome": nome,
                    "descricao": descricao,
                    "sala": sala,
                    "vagas": vagas,
                    "data_hora_inicio": ensure_timezone(data_hora_inicio),
                    "data_hora_fim": ensure_timezone(data_hora_fim),
                },
            )
            session.commit()

    def _ensure_inside_event(
        self,
        session: Session,
        data_hora_inicio: datetime,
        data_hora_fim: datetime,
    ) -> None:
        """A atividade precisa estar contida no intervalo do evento."""
        _ensure_inside_event(session, self.id_evento, data_hora_inicio, data_hora_fim)

    def add_lecturers(self, entries: list[LecturerInput]) -> None:
        """
        Adiciona ministrantes à atividade.

        O mesmo usuário não pode ministrar a atividade duas vezes (PK);
        violação vira ``DuplicateLecturer``.
        """
        query = text(
            """
            INSERT INTO ministra_atividade
                (id_usuario, id_evento, id_atividade, mini_bio, instituicao, link_lattes)
            VALUES
                (:id_usuario, :id_evento, :id_atividade, :mini_bio, :instituicao, :link_lattes)
            """
        )
        with session_maker() as session:
            session.begin()
            try:
                for entry in entries:
                    _ = session.execute(
                        query,
                        {
                            "id_usuario": entry.user.id,
                            "id_evento": self.id_evento,
                            "id_atividade": self.id,
                            "mini_bio": entry.mini_bio,
                            "instituicao": entry.instituicao,
                            "link_lattes": entry.link_lattes,
                        },
                    )
            except IntegrityError as e:
                raise DuplicateLecturer from e
            session.commit()

    def remove_lecturer(self, user_id: int) -> bool:
        """Remove um ministrante; retorna ``True`` se uma linha foi removida."""
        check_query = text(
            """
            SELECT id_usuario
            FROM ministra_atividade
            WHERE id_evento = :id_evento
              AND id_atividade = :id_atividade
              AND id_usuario <> :removing
            LIMIT 1
            """
        )

        with session_maker() as session:
            other = (
                session.execute(
                    check_query,
                    {
                        "id_evento": self.id_evento,
                        "id_atividade": self.id,
                        "removing": user_id,
                    },
                )
                .mappings()
                .first()
            )

        if other is None:
            raise ActivityWithoutLecturer
        delete_query = text(
            """
            DELETE FROM ministra_atividade
            WHERE id_usuario = :id_usuario
              AND id_evento = :id_evento
              AND id_atividade = :id_atividade
            RETURNING id_usuario
            """
        )

        with session_maker() as session:
            session.begin()
            result = session.execute(
                delete_query,
                {
                    "id_usuario": user_id,
                    "id_evento": self.id_evento,
                    "id_atividade": self.id,
                },
            )
            session.commit()
            return result.rowcount == 1

    def update_lecturer(
        self,
        user_id: int,
        mini_bio: str | None,
        instituicao: str,
        link_lattes: str | None,
    ) -> None:
        query = text(
            """
            UPDATE ministra_atividade
            SET mini_bio = :mini_bio, instituicao = :instituicao, link_lattes = :link_lattes
            WHERE id_usuario = :id_usuario
              AND id_evento = :id_evento
              AND id_atividade = :id_atividade
            """
        )
        with session_maker() as session:
            session.begin()
            _ = session.execute(
                query,
                {
                    "id_usuario": user_id,
                    "id_evento": self.id_evento,
                    "id_atividade": self.id,
                    "mini_bio": mini_bio,
                    "instituicao": instituicao,
                    "link_lattes": link_lattes,
                },
            )
            session.commit()

    def delete(self) -> bool:
        """
        Exclui a atividade, retornando ``True`` se uma linha foi removida.

        A exclusão é bloqueada quando a atividade já possui presenças
        registradas (regra: atividades não podem ser removidas depois de
        receberem presença, ``ActivityHasDependencies``); sem presenças, os
        vínculos de ministrantes são removidos junto, na mesma transação.
        """
        count_query = text(
            """
            SELECT COUNT(id_usuario) AS total
            FROM presenca_atividade
            WHERE id_evento = :id_evento AND id_atividade = :id
            """
        )
        with session_maker() as session:
            presencas = session.execute(
                count_query, {"id_evento": self.id_evento, "id": self.id}
            ).scalar_one()
        if presencas > 0:
            raise ActivityHasDependencies

        delete_query = text(
            """
            DELETE FROM atividade
            WHERE id = :id AND id_evento = :id_evento
            RETURNING id
            """
        )
        with session_maker() as session:
            session.begin()
            try:
                # ordem importa: ministrantes referenciam a atividade, então
                # os vínculos saem antes da própria atividade
                _ = session.execute(
                    text(
                        """
                        DELETE FROM ministra_atividade
                        WHERE id_evento = :id_evento AND id_atividade = :id
                        """
                    ),
                    {"id_evento": self.id_evento, "id": self.id},
                )
                result = session.execute(
                    delete_query, {"id": self.id, "id_evento": self.id_evento}
                )
            except IntegrityError as e:
                # corrida: presença registrada entre a contagem e a exclusão
                raise ActivityHasDependencies from e
            session.commit()
            return result.rowcount == 1


@dataclass
class ActivityList:
    """Coleção de atividades de um evento para a interface."""

    items: list[ActivityPreview]
    on_change: Callable

    def __post_init__(self) -> None:
        self.event_id: int | None = self.items[0].id_evento if self.items else None

    def set_event(self, event_id: int) -> None:
        """Define o evento da lista; um evento tem apenas uma numeração de atividades."""
        self.event_id = event_id
        self.items = []

    def reload(self) -> None:
        """Recarrega as atividades do evento configurado em ``set_event``."""
        if self.event_id is None:
            self.items = []
            self.on_change()
            return
        query = text(
            """
            SELECT a.id_evento, a.id, a.nome, a.sala,
                   a.data_hora_inicio, a.data_hora_fim, a.vagas
            FROM atividade a
            WHERE a.id_evento = :id_evento
            ORDER BY a.id
            """
        )
        with session_maker() as session:
            self.items = [
                ActivityPreview(**dict(row))
                for row in session.execute(
                    query, {"id_evento": self.event_id}
                ).mappings()
            ]
        self.on_change()

    def get_activity_details(self, activity_id: int, event_id: int) -> Activity:
        return get_activity(activity_id, event_id)

    def add(
        self,
        event_id: int,
        nome: str,
        descricao: str | None,
        sala: str,
        vagas: int,
        data_hora_inicio: datetime,
        data_hora_fim: datetime,
        lecturers: list[LecturerInput],
    ) -> Activity:
        """
        Cria a atividade e seus ministrantes na mesma transação.

        O ``id`` é gerado pelo banco; o horário precisa estar contido no do
        evento (``InvalidActivitySchedule``) e a regra de negócio exige ao
        menos um ministrante (``ActivityWithoutLecturer``). O mesmo usuário
        não pode ministrar a atividade duas vezes (``DuplicateLecturer``).
        """
        if not lecturers:
            raise ActivityWithoutLecturer
        query = text(
            """
            INSERT INTO atividade
                (id_evento, nome, descricao, sala, vagas, data_hora_inicio, data_hora_fim)
            VALUES
                (:id_evento, :nome, :descricao, :sala, :vagas,
                 :data_hora_inicio, :data_hora_fim)
            RETURNING id_evento, id, nome, sala, data_hora_inicio, data_hora_fim,
                     descricao, vagas
            """
        )
        lecturer_query = text(
            """
            INSERT INTO ministra_atividade
                (id_usuario, id_evento, id_atividade, mini_bio, instituicao, link_lattes)
            VALUES
                (:id_usuario, :id_evento, :id_atividade, :mini_bio, :instituicao, :link_lattes)
            """
        )
        with session_maker() as session:
            session.begin()
            _ensure_inside_event(session, event_id, data_hora_inicio, data_hora_fim)
            result = session.execute(
                query,
                {
                    "id_evento": event_id,
                    "nome": nome,
                    "descricao": descricao,
                    "sala": sala,
                    "vagas": vagas,
                    "data_hora_inicio": ensure_timezone(data_hora_inicio),
                    "data_hora_fim": ensure_timezone(data_hora_fim),
                },
            )
            # consome o RETURNING antes de executar as demais statements na
            # mesma conexão (o cursor não aceita outra query com resultado
            # pendente)
            row = dict(result.mappings().first())
            try:
                for entry in lecturers:
                    _ = session.execute(
                        lecturer_query,
                        {
                            "id_usuario": entry.user.id,
                            "id_evento": event_id,
                            "id_atividade": row["id"],
                            "mini_bio": entry.mini_bio,
                            "instituicao": entry.instituicao,
                            "link_lattes": entry.link_lattes,
                        },
                    )
            except IntegrityError as e:
                raise DuplicateLecturer from e
            session.commit()
        self.on_change()
        return Activity(lecturers=get_lecturers(row["id_evento"], row["id"]), **row)

    def delete_activity(self, activity_id: int) -> bool:
        """Exclui a atividade pelo id; retorna ``True`` se algo foi removido."""
        deleted = delete_activity(activity_id)
        if deleted:
            self.on_change()
        return deleted


def get_activity(activity_id: int, event_id: int | None = None) -> Activity:
    """
    Busca os detalhes de uma atividade.

    ``activity_id`` é único no banco; ``event_id`` é opcional e, quando dado,
    restringe a busca a um evento específico.
    """
    event_clause = "AND a.id_evento = :id_evento" if event_id is not None else ""
    query = text(
        f"""
        SELECT a.id_evento, a.id, a.nome, a.sala,
               a.data_hora_inicio, a.data_hora_fim, a.descricao, a.vagas
        FROM atividade a
        WHERE a.id = :id {event_clause}
        LIMIT 1
        """
    )
    params: dict[str, int] = {"id": activity_id}
    if event_id is not None:
        params["id_evento"] = event_id
    with session_maker() as session:
        row = session.execute(query, params).mappings().first()
    if row is None:
        raise ActivityNotFound
    base = dict(row)
    detail = Activity(lecturers=[], **base)
    detail.lecturers = get_lecturers(event_id or base["id_evento"], activity_id)
    return detail


def delete_activity(activity_id: int) -> bool:
    """
    Exclui uma atividade, retornando ``True`` se uma linha foi removida.

    A exclusão é bloqueada quando a atividade já possui presenças
    registradas (``ActivityHasDependencies``); os vínculos de ministrantes
    são removidos junto. ``ActivityNotFound`` se a atividade não existir.
    """
    activity = get_activity(activity_id)
    return activity.delete()


def get_lecturers(event_id: int, activity_id: int) -> list[Lecturer]:
    """Ministrantes de uma atividade, com dados do usuário para exibição."""
    query = text(
        """
        SELECT m.id_usuario, m.id_evento, m.id_atividade,
               m.mini_bio, m.instituicao, m.link_lattes,
               v.id, v.nome, v.cpf::text, v.email, v.data_nascimento,
               v.papel, v.idade::int
        FROM ministra_atividade m
        JOIN usuario_com_idade v ON v.id = m.id_usuario
        WHERE m.id_evento = :id_evento AND m.id_atividade = :id_atividade
        """
    )
    with session_maker() as session:
        rows = session.execute(
            query, {"id_evento": event_id, "id_atividade": activity_id}
        ).mappings()
        return [_row_to_lecturer(r) for r in rows]


def _row_to_lecturer(r) -> Lecturer:
    """Constrói um ``Lecturer`` de uma linha de ``ministra_atividade`` + usuário."""
    return Lecturer(
        id_usuario=r["id_usuario"],
        id_evento=r["id_evento"],
        id_atividade=r["id_atividade"],
        mini_bio=r["mini_bio"],
        instituicao=r["instituicao"],
        link_lattes=r["link_lattes"],
        user=User(
            id=r["id"],
            nome=r["nome"],
            cpf=r["cpf"],
            email=r["email"],
            data_nascimento=r["data_nascimento"],
            papel=r["papel"],
            idade=r["idade"],
        ),
    )


def get_event_activities(event_id: int) -> list[Activity]:
    """
    Todas as atividades de um evento, com descrição, vagas e ministrantes,
    ordenadas pelo horário de início.

    Usa duas consultas (atividades e ministrantes do evento inteiro) em vez
    de uma por atividade.
    """
    activities_query = text(
        """
        SELECT a.id_evento, a.id, a.nome, a.sala,
               a.data_hora_inicio, a.data_hora_fim, a.descricao, a.vagas
        FROM atividade a
        WHERE a.id_evento = :id_evento
        ORDER BY a.data_hora_inicio, a.id
        """
    )
    lecturers_query = text(
        """
        SELECT m.id_usuario, m.id_evento, m.id_atividade,
               m.mini_bio, m.instituicao, m.link_lattes,
               v.id, v.nome, v.cpf::text, v.email, v.data_nascimento,
               v.papel, v.idade::int
        FROM ministra_atividade m
        JOIN usuario_com_idade v ON v.id = m.id_usuario
        WHERE m.id_evento = :id_evento
        ORDER BY v.nome
        """
    )
    params = {"id_evento": event_id}
    with session_maker() as session:
        activities = [
            Activity(lecturers=[], **dict(row))
            for row in session.execute(activities_query, params).mappings()
        ]
        by_id = {a.id: a for a in activities}
        for row in session.execute(lecturers_query, params).mappings():
            by_id[row["id_atividade"]].lecturers.append(_row_to_lecturer(row))
    return activities
