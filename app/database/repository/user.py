"""
Operações sobre a entidade de usuário.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from pwdlib.hashers.argon2 import Argon2Hasher
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.database import session_maker
from app.database.repository.inscription import (
    InscricaoEvento,
    PresencaAtividade,
)
from app.exceptions import (
    UsuarioComDependencias,
    UsuarioNaoEncontrado,
    UsuarioRepetido,
)

# Utilizando o algoritmo Argon2Id para criptografar as senhas
pwd_context = PasswordHash((Argon2Hasher(),))

Papel = Literal["administrador", "associado"]


@dataclass
class Usuario:
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

    @classmethod
    def de_linha(cls, row: Mapping[str, Any]) -> "Usuario":
        """Constrói um ``Usuario`` de uma linha de ``usuario_com_idade``."""
        return cls(**dict(row))

    def atualizar(self, nome: str, email: str, cpf: str, data_nascimento: date) -> None:
        """
        Atualiza os dados do usuário. A unicidade de CPF e e-mail é garantida
        pelo banco; violação vira ``UsuarioRepetido``.
        """
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
                raise UsuarioRepetido from e
            session.commit()

    def excluir(self) -> bool:
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
                raise UsuarioComDependencias from e
            if result.rowcount != 1:
                session.rollback()
                return False
            else:
                session.commit()
                return True

    def listar_inscricoes(self) -> list[InscricaoEvento]:
        """Inscrições do usuário em eventos, com dados do evento para exibição."""

        query = text(
            """
            SELECT i.id_usuario, i.id_evento, i.data_inscricao, i.status,
                   i.valor, i.meia, i.comprovante_usuario, i.comentario_administrador,
                   e.nome AS evento_nome, e.data_hora_inicio, e.data_hora_fim
            FROM inscricao_evento i
            JOIN evento e ON e.id = i.id_evento
            WHERE i.id_usuario = :id_usuario
            ORDER BY i.id_evento
            """
        )

        with session_maker() as session:
            rows = session.execute(query, {"id_usuario": self.id}).mappings()
            return [InscricaoEvento.de_linha(r) for r in rows]

    def listar_presencas(self, evento_id: int | None = None) -> list[PresencaAtividade]:
        """
        Atividades em que o usuário esteve presente, com dados do evento e da
        atividade. ``evento_id`` é opcional e restringe a busca a um evento.
        """

        evento_clause = "AND p.id_evento = :evento_id" if evento_id is not None else ""
        query = text(
            f"""
            SELECT p.id_usuario, p.id_evento, p.id_atividade,
                   e.nome AS evento_nome,
                   a.nome AS atividade_nome, a.sala
            FROM presenca_atividade p
            JOIN evento e ON e.id = p.id_evento
            JOIN atividade a ON a.id_evento = p.id_evento
                     AND a.id = p.id_atividade
            WHERE p.id_usuario = :id_usuario {evento_clause}
            ORDER BY p.id_evento, p.id_atividade
            """
        )
        params: dict[str, int] = {"id_usuario": self.id}
        if evento_id is not None:
            params["evento_id"] = evento_id

        with session_maker() as session:
            rows = session.execute(query, params).mappings()
            return [PresencaAtividade.de_linha(r) for r in rows]


def listar_usuarios() -> list[Usuario]:
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
        return [Usuario.de_linha(row) for row in session.execute(query).mappings()]


def obter_usuario_por_id(usuario_id: int) -> Usuario:
    """Busca um usuário por id; lança ``UsuarioNaoEncontrado`` se não existir."""
    query = text(
        """
        SELECT id, nome, cpf::text, email, data_nascimento,
               papel, idade::int
        FROM usuario_com_idade
        WHERE id = :usuario_id
        LIMIT 1
        """
    )
    with session_maker() as session:
        row = session.execute(query, {"usuario_id": usuario_id}).mappings().first()
    if row is None:
        raise UsuarioNaoEncontrado
    return Usuario.de_linha(row)


def criar_usuario(
    nome: str,
    cpf: str,
    email: str,
    senha: str,
    data_nascimento: date,
    papel: Papel = "associado",
) -> Usuario:
    """
    Cria um usuário autenticável.

    A senha é armazenada apenas como hash (argon2id via pwdlib). A unicidade
    de CPF e e-mail é garantida pelo banco; violações viram
    ``UsuarioRepetido``.
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
                    "senha_hash": pwd_context.hash(senha),
                    "papel": papel,
                    "data_nascimento": data_nascimento,
                },
            )
        except IntegrityError as e:
            raise UsuarioRepetido from e
        session.commit()
        row = result.mappings().first()
    return Usuario.de_linha(row)


def autenticar_usuario(email: str, senha: str) -> Usuario | None:
    """Valida credenciais; retorna o ``Usuario`` ou ``None`` se forem inválidas."""

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
        ok = pwd_context.verify(senha, senha_hash)
    except UnknownHashError:
        return None
    if not ok:
        return None
    return Usuario.de_linha(row)
