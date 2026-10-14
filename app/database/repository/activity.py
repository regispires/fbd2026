"""
Operações sobre atividades e os ministrantes.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import session_maker
from app.database.repository import ensure_utc
from app.database.repository.user import User
from app.exceptions import (
    ActivityHasDependencies,
    ActivityNotFound,
    ActivityWithoutLecturer,
    DuplicateActivityRegistration,
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
    if (
        data_hora_inicio < row["data_hora_inicio"]
        or data_hora_fim > row["data_hora_fim"]
    ):
        raise InvalidActivitySchedule


@dataclass
class Lecturer:
    """Linha da ``ministra_atividade`` com os dados do usuário para exibição."""

    id_usuario: UUID
    id_evento: int
    numero_atividade: int
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

    Espelha as colunas de ``atividade`` sem as chaves compostas; a validação
    de que o horário está contido no do evento é feita no ``create_event``.
    """

    numero: int
    nome: str
    descricao: str | None
    sala: str
    vagas: int
    data_hora_inicio: datetime
    data_hora_fim: datetime


@dataclass
class ActivityPreview:
    """Campos resumidos da atividade, para exibição em listas."""

    id_evento: int
    numero: int
    nome: str
    sala: str
    data_hora_inicio: datetime
    data_hora_fim: datetime


@dataclass
class Activity(ActivityPreview):
    """Atividade completa, incluindo a descrição, as vagas e os ministrantes."""

    lecturers: list[Lecturer]
    descricao: str | None
    vagas: int

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
            WHERE numero = :numero AND id_evento = :id_evento
            """
        )
        with session_maker() as session:
            session.begin()
            self._ensure_inside_event(session, data_hora_inicio, data_hora_fim)
            _ = session.execute(
                query,
                {
                    "numero": self.numero,
                    "id_evento": self.id_evento,
                    "nome": nome,
                    "descricao": descricao,
                    "sala": sala,
                    "vagas": vagas,
                    "data_hora_inicio": ensure_utc(data_hora_inicio),
                    "data_hora_fim": ensure_utc(data_hora_fim),
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
        query = text(
            """
            INSERT INTO ministra_atividade
                (id_usuario, id_evento, numero_atividade, mini_bio, instituicao, link_lattes)
            VALUES
                (:id_usuario, :id_evento, :numero_atividade, :mini_bio, :instituicao, :link_lattes)
            """
        )
        with session_maker() as session:
            session.begin()
            for entry in entries:
                _ = session.execute(
                    query,
                    {
                        "id_usuario": entry.user.id,
                        "id_evento": self.id_evento,
                        "numero_atividade": self.numero,
                        "mini_bio": entry.mini_bio,
                        "instituicao": entry.instituicao,
                        "link_lattes": entry.link_lattes,
                    },
                )
            session.commit()

    def remove_lecturer(self, user_id: UUID) -> bool:
        """Remove um ministrante; retorna ``True`` se uma linha foi removida."""
        check_query = text(
            """
            SELECT id_usuario
            FROM ministra_atividade
            WHERE id_evento = :id_evento
              AND numero_atividade = :numero_atividade
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
                        "numero_atividade": self.numero,
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
              AND numero_atividade = :numero_atividade
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
                    "numero_atividade": self.numero,
                },
            )
            session.commit()
            return result.rowcount == 1

    def update_lecturer(
        self,
        user_id: UUID,
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
              AND numero_atividade = :numero_atividade
            """
        )
        with session_maker() as session:
            session.begin()
            _ = session.execute(
                query,
                {
                    "id_usuario": user_id,
                    "id_evento": self.id_evento,
                    "numero_atividade": self.numero,
                    "mini_bio": mini_bio,
                    "instituicao": instituicao,
                    "link_lattes": link_lattes,
                },
            )
            session.commit()


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
            SELECT a.id_evento, a.numero, a.nome, a.sala,
                   a.data_hora_inicio, a.data_hora_fim
            FROM atividade a
            WHERE a.id_evento = :id_evento
            ORDER BY a.numero
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

    def get_activity_details(self, number: int, event_id: int) -> Activity:
        return get_activity(number, event_id)

    def add(
        self,
        event_id: int,
        numero: int,
        nome: str,
        descricao: str | None,
        sala: str,
        vagas: int,
        data_hora_inicio: datetime,
        data_hora_fim: datetime,
    ) -> Activity:
        """
        Cria a atividade, validando o intervalo do evento e o número único
        na mesma transação da escrita.
        """
        query = text(
            """
            INSERT INTO atividade
                (numero, id_evento, nome, descricao, sala, vagas, data_hora_inicio, data_hora_fim)
            VALUES
                (:numero, :id_evento, :nome, :descricao, :sala, :vagas,
                 :data_hora_inicio, :data_hora_fim)
            RETURNING id_evento, numero, nome, sala, data_hora_inicio, data_hora_fim,
                     descricao, vagas
            """
        )
        with session_maker() as session:
            session.begin()
            _ensure_inside_event(session, event_id, data_hora_inicio, data_hora_fim)
            try:
                result = session.execute(
                    query,
                    {
                        "numero": numero,
                        "id_evento": event_id,
                        "nome": nome,
                        "descricao": descricao,
                        "sala": sala,
                        "vagas": vagas,
                        "data_hora_inicio": ensure_utc(data_hora_inicio),
                        "data_hora_fim": ensure_utc(data_hora_fim),
                    },
                )
            except IntegrityError as e:
                raise DuplicateActivityRegistration from e
            session.commit()
            row = result.mappings().first()
        self.on_change()
        return Activity(lecturers=[], **dict(row))

    def delete_activity(self, numero: int) -> bool:
        """Exclui a atividade pelo número; retorna ``True`` se algo foi removido."""
        query = text("DELETE FROM atividade WHERE numero = :numero RETURNING numero")
        with session_maker() as session:
            session.begin()
            try:
                result = session.execute(query, {"numero": numero})
            except IntegrityError as e:
                raise ActivityHasDependencies from e
            session.commit()
            deleted = result.rowcount == 1
        if deleted:
            self.on_change()
        return deleted


def get_activity(numero: int, event_id: int | None = None) -> Activity:
    """
    Busca os detalhes de uma atividade.

    ``numero`` é único no banco; ``event_id`` é opcional e, quando dado,
    restringe a busca a um evento específico.
    """
    event_clause = "AND a.id_evento = :id_evento" if event_id is not None else ""
    query = text(
        f"""
        SELECT a.id_evento, a.numero, a.nome, a.sala,
               a.data_hora_inicio, a.data_hora_fim, a.descricao, a.vagas
        FROM atividade a
        WHERE a.numero = :numero {event_clause}
        LIMIT 1
        """
    )
    params: dict[str, int] = {"numero": numero}
    if event_id is not None:
        params["id_evento"] = event_id
    with session_maker() as session:
        row = session.execute(query, params).mappings().first()
    if row is None:
        raise ActivityNotFound
    base = dict(row)
    detail = Activity(lecturers=[], **base)
    detail.lecturers = get_lecturers(event_id or base["id_evento"], numero)
    return detail


def get_lecturers(event_id: int, numero: int) -> list[Lecturer]:
    """Ministrantes de uma atividade, com dados do usuário para exibição."""
    query = text(
        """
        SELECT m.id_usuario, m.id_evento, m.numero_atividade,
               m.mini_bio, m.instituicao, m.link_lattes,
               u.id, u.nome, u.cpf::text, u.email, u.data_nascimento, u.papel,
               v.idade::int
        FROM ministra_atividade m
        JOIN usuario u ON u.id = m.id_usuario
        JOIN usuario_com_idade v ON v.id = m.id_usuario
        WHERE m.id_evento = :id_evento AND m.numero_atividade = :numero
        """
    )
    with session_maker() as session:
        rows = session.execute(
            query, {"id_evento": event_id, "numero": numero}
        ).mappings()
    return [
        Lecturer(
            id_usuario=r["id_usuario"],
            id_evento=r["id_evento"],
            numero_atividade=r["numero_atividade"],
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
        for r in rows
    ]
