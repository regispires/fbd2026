"""
Operações sobre a entidade de usuário.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Literal

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from pwdlib.hashers.argon2 import Argon2Hasher
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.database import session_maker
from app.database.repository import as_bytes
from app.database.repository.inscription import (
    ActivityAttendance,
    EventInscription,
)
from app.exceptions import (
    DuplicateUserRegistration,
    UserHasDependencies,
    UserNotFound,
)

# Utilizando o algoritmo Argon2Id para criptografar as senhas
pwd_context = PasswordHash((Argon2Hasher(),))

Papel = Literal["administrador", "associado"]


@dataclass
class User:
    """
    Representa a tabela `usuario`
    """

    id: int
    nome: str
    cpf: str
    email: str
    data_nascimento: date
    papel: Papel
    idade: int

    def update(self, nome: str, email: str, cpf: str, data_nascimento: date) -> None:
        query = text(
            """
            UPDATE usuario
            SET nome = :nome, email = :email, cpf = :cpf, data_nascimento = :data_nascimento
            WHERE id = :id
            """
        )
        with session_maker() as session:
            session.begin()
            try:
                _ = session.execute(
                    query,
                    {
                        "id": self.id,
                        "nome": nome,
                        "email": email,
                        "cpf": cpf,
                        "data_nascimento": data_nascimento,
                    },
                )
            except IntegrityError as e:
                raise DuplicateUserRegistration from e
            session.commit()

    def delete(self) -> bool:
        """
        Exclui o usuário, retornando ``True`` se uma linha foi removida.

        Caso ainda existam inscrições ou atividades vinculadas a esse usuário a exclusão falha
        """
        query = text("DELETE FROM usuario WHERE id = :id RETURNING id")
        with session_maker() as session:
            session.begin()
            try:
                result = session.execute(query, {"id": self.id})
            except IntegrityError as e:
                raise UserHasDependencies from e
            if result.rowcount != 1:
                session.rollback()
                return False
            else:
                session.commit()
                return True

    def get_event_inscriptions(self) -> list[EventInscription]:
        """Inscrições do usuário em eventos, com dados do evento para exibição."""

        query = text(
            """
            SELECT i.id_usuario, i.id_evento, i.data_inscricao, i.status,
                   i.valor, i.meia, i.comprovante_usuario, i.comentario_administrador,
                   e.nome AS event_nome, e.data_hora_inicio, e.data_hora_fim
            FROM inscricao_evento i
            JOIN evento e ON e.id = i.id_evento
            WHERE i.id_usuario = :id_usuario
            ORDER BY i.id_evento
            """
        )

        with session_maker() as session:
            rows = session.execute(query, {"id_usuario": self.id}).mappings()
            return [
                EventInscription(
                    user_id=r["id_usuario"],
                    event_id=r["id_evento"],
                    data_inscricao=r["data_inscricao"],
                    status=r["status"],
                    valor=r["valor"],
                    meia=r["meia"],
                    comprovante_usuario=as_bytes(r["comprovante_usuario"]),
                    comentario_administrador=r["comentario_administrador"],
                    event_nome=r["event_nome"],
                    data_hora_inicio=r["data_hora_inicio"],
                    data_hora_fim=r["data_hora_fim"],
                )
                for r in rows
            ]

    def get_attendances(self, event_id: int | None = None) -> list[ActivityAttendance]:
        """
        Atividades em que o usuário esteve presente, com dados do evento e da
        atividade. ``event_id`` é opcional e restringe a busca a um evento.
        """

        event_clause = "AND p.id_evento = :event_id" if event_id is not None else ""
        query = text(
            f"""
            SELECT p.id_usuario, p.id_evento, p.id_atividade,
                   e.nome AS event_nome,
                   a.nome AS activity_nome, a.sala
            FROM presenca_atividade p
            JOIN evento e ON e.id = p.id_evento
            JOIN atividade a ON a.id_evento = p.id_evento
                     AND a.id = p.id_atividade
            WHERE p.id_usuario = :id_usuario {event_clause}
            ORDER BY p.id_evento, p.id_atividade
            """
        )
        params: dict[str, int] = {"id_usuario": self.id}
        if event_id is not None:
            params["event_id"] = event_id

        with session_maker() as session:
            rows = session.execute(query, params).mappings()
            return [
                ActivityAttendance(
                    user_id=r["id_usuario"],
                    event_id=r["id_evento"],
                    id_atividade=r["id_atividade"],
                    event_nome=r["event_nome"],
                    activity_nome=r["activity_nome"],
                    sala=r["sala"],
                )
                for r in rows
            ]


@dataclass
class UserList:
    """Coleção de usuários para painéis administrativos da interface."""

    items: list[User]
    on_change: Callable

    def reload(self) -> None:
        self.items = get_users()
        self.on_change()


def get_users() -> list[User]:
    """Todos os usuários, ordenados pelo nome (seleção de ministrantes)."""
    query = text(
        """
        SELECT id, nome, cpf::text, email, data_nascimento,
               papel, idade::int
        FROM usuario_com_idade
        ORDER BY nome
        """
    )
    with session_maker() as session:
        return [User(**dict(row)) for row in session.execute(query).mappings()]


def get_user(user_id: int) -> User:
    """Busca um usuário por id; lança ``UserNotFound`` se não existir."""
    query = text(
        """
        SELECT id, nome, cpf::text, email, data_nascimento,
               papel, idade::int
        FROM usuario_com_idade
        WHERE id = :user_id
        LIMIT 1
        """
    )
    with session_maker() as session:
        row = session.execute(query, {"user_id": user_id}).mappings().first()
    if row is None:
        raise UserNotFound
    return User(**dict(row))


def create_user(
    nome: str,
    cpf: str,
    email: str,
    password: str,
    data_nascimento: date,
    papel: Papel = "associado",
) -> User:
    """
    Cria um usuário autenticável.

    A senha é armazenada apenas como hash (argon2id via pwdlib). A unicidade
    de CPF e e-mail é garantida pelo banco; violações viram
    ``DuplicateUserRegistration``.
    """

    query = text(
        """
        INSERT INTO usuario (nome, cpf, email, senha_hash, papel, data_nascimento)
        VALUES (:nome, :cpf, :email, :senha_hash, :papel, :data_nascimento)
        RETURNING id, nome, cpf::text AS cpf, email, data_nascimento, papel,
                  EXTRACT(YEARS FROM AGE(data_nascimento))::int AS idade
        """
    )

    with session_maker() as session:
        session.begin()
        try:
            result = session.execute(
                query,
                {
                    "nome": nome,
                    "cpf": cpf,
                    "email": email,
                    "senha_hash": pwd_context.hash(password),
                    "papel": papel,
                    "data_nascimento": data_nascimento,
                },
            )
        except IntegrityError as e:
            raise DuplicateUserRegistration from e
        session.commit()
        row = result.mappings().first()
    return User(**dict(row))


def authenticate_user(email: str, password: str) -> User | None:
    """Valida credenciais; retorna o ``User`` ou ``None`` se forem inválidas."""

    query = text(
        """
        SELECT u.id, u.nome, u.cpf::text, u.email, u.data_nascimento,
               u.papel, EXTRACT(YEARS FROM AGE(u.data_nascimento)) AS idade, u.senha_hash
        FROM usuario u
        WHERE u.email = :email
        LIMIT 1
        """
    )

    with session_maker() as session:
        row = session.execute(query, {"email": email}).mappings().first() or {}

    row = dict(row)
    # a senha é verificada mesmo que o usuário exista, isso não é necessário em um teste local,
    # mas evita ataques de temporização (https://pt.wikipedia.org/wiki/Ataque_de_temporiza%C3%A7%C3%A3o)
    senha_hash = row.pop("senha_hash", "")
    try:
        ok = pwd_context.verify(password, senha_hash)
    except UnknownHashError:
        return None
    if not ok:
        return None
    return User(**dict(row))
