"""
Operações sobre atividades e os ministrantes.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import session_maker
from app.database.repository import contar_linhas, contido_em, garantir_timezone
from app.database.repository.user import Usuario
from app.exceptions import (
    AtividadeComDependencias,
    AtividadeNaoEncontrada,
    AtividadeSemMinistrante,
    EventoNaoEncontrado,
    EventoSemAtividade,
    HorarioAtividadeInvalido,
    MinistranteRepetido,
)


def _garantir_dentro_do_evento(
    session: Session,
    evento_id: int,
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
    row = session.execute(query, {"id_evento": evento_id}).mappings().first()
    if row is None:
        raise EventoNaoEncontrado
    if not contido_em(
        data_hora_inicio, data_hora_fim, row["data_hora_inicio"], row["data_hora_fim"]
    ):
        raise HorarioAtividadeInvalido


@dataclass
class Ministrante:
    """Linha da ``ministra_atividade`` com os dados do usuário para exibição."""

    id_usuario: int
    id_evento: int
    id_atividade: int
    mini_bio: str | None
    instituicao: str
    link_lattes: str | None
    usuario: Usuario

    @classmethod
    def de_linha(cls, row: Mapping[str, Any]) -> "Ministrante":
        """Constrói um ``Ministrante`` de uma linha de ``ministra_atividade`` + usuário."""
        return cls(
            id_usuario=row["id_usuario"],
            id_evento=row["id_evento"],
            id_atividade=row["id_atividade"],
            mini_bio=row["mini_bio"],
            instituicao=row["instituicao"],
            link_lattes=row["link_lattes"],
            usuario=Usuario(
                id=row["id"],
                nome=row["nome"],
                cpf=row["cpf"],
                email=row["email"],
                data_nascimento=row["data_nascimento"],
                papel=row["papel"],
                sexo=row["sexo"],
                idade=row["idade"],
            ),
        )


@dataclass
class EntradaMinistrante:
    """
    Entrada para ``Atividade.adicionar_ministrantes``.

    Espelha a nulabilidade da ``ministra_atividade``: ``instituicao`` é
    obrigatório, ``mini_bio`` e ``link_lattes`` são opcionais.
    """

    usuario: Usuario
    mini_bio: str | None
    instituicao: str
    link_lattes: str | None


@dataclass
class EntradaAtividade:
    """
    Entrada para criação/edição de atividades.

    Espelha as colunas de ``atividade`` sem as chaves (``id`` é gerado pelo
    banco e ``id_evento`` é o do evento); a validação de que o horário está
    contido no do evento é feita no repositório, na transação da escrita. A
    regra de negócio exige ao menos um ministrante por atividade — junto ao
    evento, o campo ``ministrantes`` precisa estar preenchido.

    É o modelo único dos valores coletados do formulário de atividade (os
    dialogs passam a instância direto ao repositório, via ``parametros``).
    """

    nome: str
    descricao: str | None
    sala: str
    vagas: int
    data_hora_inicio: datetime
    data_hora_fim: datetime
    ministrantes: list[EntradaMinistrante] = field(default_factory=list)

    @classmethod
    def de_atividade(cls, atividade: "Atividade") -> "EntradaAtividade":
        """Extrai os campos editáveis de uma atividade (pré-preenchimento)."""
        return cls(
            nome=atividade.nome,
            descricao=atividade.descricao,
            sala=atividade.sala,
            vagas=atividade.vagas,
            data_hora_inicio=atividade.data_hora_inicio,
            data_hora_fim=atividade.data_hora_fim,
        )

    def parametros(self) -> dict[str, Any]:
        """Kwargs de escrita (sem os ministrantes, que o chamador trata à parte)."""
        return dict(
            nome=self.nome,
            descricao=self.descricao,
            sala=self.sala,
            vagas=self.vagas,
            data_hora_inicio=self.data_hora_inicio,
            data_hora_fim=self.data_hora_fim,
        )


@dataclass
class PreviaAtividade:
    """Campos resumidos da atividade, para exibição em listas."""

    id_evento: int
    id: int
    nome: str
    sala: str
    data_hora_inicio: datetime
    data_hora_fim: datetime
    vagas: int


@dataclass
class Atividade(PreviaAtividade):
    """Atividade completa, incluindo a descrição e os ministrantes."""

    ministrantes: list[Ministrante]
    descricao: str | None

    @classmethod
    def de_linha(
        cls, row: Mapping[str, Any], ministrantes: list[Ministrante] | None = None
    ) -> "Atividade":
        """Constrói uma ``Atividade`` de uma linha; os ministrantes são opcionais."""
        return cls(ministrantes=ministrantes or [], **dict(row))

    def atualizar(
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
            _garantir_dentro_do_evento(
                session, self.id_evento, data_hora_inicio, data_hora_fim
            )
            _ = session.execute(
                query,
                {
                    "id": self.id,
                    "id_evento": self.id_evento,
                    "nome": nome,
                    "descricao": descricao,
                    "sala": sala,
                    "vagas": vagas,
                    "data_hora_inicio": garantir_timezone(data_hora_inicio),
                    "data_hora_fim": garantir_timezone(data_hora_fim),
                },
            )
            session.commit()

    def adicionar_ministrantes(self, entradas: list[EntradaMinistrante]) -> None:
        """
        Adiciona ministrantes à atividade.

        O mesmo usuário não pode ministrar a atividade duas vezes (PK);
        violação vira ``MinistranteRepetido``.
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
                for entrada in entradas:
                    _ = session.execute(
                        query,
                        {
                            "id_usuario": entrada.usuario.id,
                            "id_evento": self.id_evento,
                            "id_atividade": self.id,
                            "mini_bio": entrada.mini_bio,
                            "instituicao": entrada.instituicao,
                            "link_lattes": entrada.link_lattes,
                        },
                    )
            except IntegrityError as e:
                raise MinistranteRepetido from e
            session.commit()

    def remover_ministrante(self, usuario_id: int) -> bool:
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
            outro = (
                session.execute(
                    check_query,
                    {
                        "id_evento": self.id_evento,
                        "id_atividade": self.id,
                        "removing": usuario_id,
                    },
                )
                .mappings()
                .first()
            )

        if outro is None:
            raise AtividadeSemMinistrante
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
                    "id_usuario": usuario_id,
                    "id_evento": self.id_evento,
                    "id_atividade": self.id,
                },
            )
            session.commit()
            return result.rowcount == 1

    def atualizar_ministrante(
        self,
        usuario_id: int,
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
                    "id_usuario": usuario_id,
                    "id_evento": self.id_evento,
                    "id_atividade": self.id,
                    "mini_bio": mini_bio,
                    "instituicao": instituicao,
                    "link_lattes": link_lattes,
                },
            )
            session.commit()

    def excluir(self) -> bool:
        """
        Exclui a atividade, retornando ``True`` se uma linha foi removida.

        A exclusão é bloqueada quando a atividade já possui presenças
        registradas (regra: atividades não podem ser removidas depois de
        receberem presença, ``AtividadeComDependencias``) e quando é a única
        do evento (regra: todo evento precisa de ao menos uma,
        ``EventoSemAtividade``). ``AtividadeNaoEncontrada`` se a instância
        não existir mais. Sem bloqueios, os vínculos de ministrantes são
        removidos junto, na mesma transação.
        """
        presencas = contar_linhas(
            """
            SELECT COUNT(id_usuario) AS total
            FROM presenca_atividade
            WHERE id_evento = :id_evento AND id_atividade = :id
            """,
            {"id_evento": self.id_evento, "id": self.id},
        )
        if presencas > 0:
            raise AtividadeComDependencias

        delete_query = text(
            """
            DELETE FROM atividade
            WHERE id = :id AND id_evento = :id_evento
            RETURNING id
            """
        )
        with session_maker() as session:
            session.begin()
            # regras contadas na mesma transação do DELETE (janela de corrida
            # menor do que a da contagem prévia): o evento precisa manter ao
            # menos uma atividade (restantes == 1 -> ``EventoSemAtividade``)
            # e uma atividade sumida (restantes == 0) é tratada como
            # inexistente
            restantes = session.execute(
                text(
                    """
                    SELECT COUNT(id) AS total
                    FROM atividade
                    WHERE id_evento = :id_evento
                    """
                ),
                {"id_evento": self.id_evento},
            ).scalar_one()
            if restantes == 0:
                raise AtividadeNaoEncontrada
            if restantes == 1:
                raise EventoSemAtividade
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
                raise AtividadeComDependencias from e
            session.commit()
            return result.rowcount == 1


def listar_atividades(evento_id: int) -> list[PreviaAtividade]:
    """Prévias das atividades de um evento (listagem), ordenadas pelo id."""
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
        return [
            PreviaAtividade(**dict(row))
            for row in session.execute(query, {"id_evento": evento_id}).mappings()
        ]


def obter_atividade(atividade_id: int, evento_id: int | None = None) -> Atividade:
    """
    Busca os detalhes de uma atividade.

    ``atividade_id`` é único no banco; ``evento_id`` é opcional e, quando
    dado, restringe a busca a um evento específico.
    """
    evento_clause = "AND a.id_evento = :id_evento" if evento_id is not None else ""
    query = text(
        f"""
        SELECT a.id_evento, a.id, a.nome, a.sala,
               a.data_hora_inicio, a.data_hora_fim, a.descricao, a.vagas
        FROM atividade a
        WHERE a.id = :id {evento_clause}
        LIMIT 1
        """
    )
    params: dict[str, int] = {"id": atividade_id}
    if evento_id is not None:
        params["id_evento"] = evento_id
    with session_maker() as session:
        row = session.execute(query, params).mappings().first()
    if row is None:
        raise AtividadeNaoEncontrada
    atividade = Atividade.de_linha(row)
    atividade.ministrantes = listar_ministrantes(
        evento_id or atividade.id_evento, atividade_id
    )
    return atividade


def excluir_atividade(atividade_id: int) -> bool:
    """
    Exclui uma atividade, retornando ``True`` se uma linha foi removida.

    A exclusão é bloqueada quando a atividade já possui presenças
    registradas (``AtividadeComDependencias``) e quando é a única do evento
    (``EventoSemAtividade``); os vínculos de ministrantes são removidos
    junto. ``AtividadeNaoEncontrada`` se a atividade não existir.
    """
    atividade = obter_atividade(atividade_id)
    return atividade.excluir()


def listar_ministrantes(evento_id: int, atividade_id: int) -> list[Ministrante]:
    """Ministrantes de uma atividade, com dados do usuário para exibição."""
    query = text(
        """
        SELECT m.id_usuario, m.id_evento, m.id_atividade,
               m.mini_bio, m.instituicao, m.link_lattes,
               v.id, v.nome, v.cpf::text, v.email, v.data_nascimento,
               v.papel, v.sexo::text, v.idade::int
        FROM ministra_atividade m
        JOIN usuario_com_idade v ON v.id = m.id_usuario
        WHERE m.id_evento = :id_evento AND m.id_atividade = :id_atividade
        """
    )
    with session_maker() as session:
        rows = session.execute(
            query, {"id_evento": evento_id, "id_atividade": atividade_id}
        ).mappings()
        return [Ministrante.de_linha(r) for r in rows]


def criar_atividade(evento_id: int, entrada: EntradaAtividade) -> Atividade:
    """
    Cria a atividade e seus ministrantes na mesma transação.

    O ``id`` é gerado pelo banco; o horário precisa estar contido no do
    evento (``HorarioAtividadeInvalido``) e a regra de negócio exige ao
    menos um ministrante (``AtividadeSemMinistrante``). O mesmo usuário
    não pode ministrar a atividade duas vezes (``MinistranteRepetido``).
    """
    if not entrada.ministrantes:
        raise AtividadeSemMinistrante
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
    ministrante_query = text(
        """
        INSERT INTO ministra_atividade
            (id_usuario, id_evento, id_atividade, mini_bio, instituicao, link_lattes)
        VALUES
            (:id_usuario, :id_evento, :id_atividade, :mini_bio, :instituicao, :link_lattes)
        """
    )
    with session_maker() as session:
        session.begin()
        _garantir_dentro_do_evento(
            session, evento_id, entrada.data_hora_inicio, entrada.data_hora_fim
        )
        params = {"id_evento": evento_id, **entrada.parametros()}
        params["data_hora_inicio"] = garantir_timezone(entrada.data_hora_inicio)
        params["data_hora_fim"] = garantir_timezone(entrada.data_hora_fim)
        result = session.execute(query, params)
        # consome o RETURNING antes de executar as demais statements na
        # mesma conexão (o cursor não aceita outra query com resultado
        # pendente)
        row = dict(result.mappings().first())
        try:
            for ministrante in entrada.ministrantes:
                _ = session.execute(
                    ministrante_query,
                    {
                        "id_usuario": ministrante.usuario.id,
                        "id_evento": evento_id,
                        "id_atividade": row["id"],
                        "mini_bio": ministrante.mini_bio,
                        "instituicao": ministrante.instituicao,
                        "link_lattes": ministrante.link_lattes,
                    },
                )
        except IntegrityError as e:
            raise MinistranteRepetido from e
        session.commit()
    return Atividade.de_linha(
        row, ministrantes=listar_ministrantes(row["id_evento"], row["id"])
    )


def listar_atividades_com_ministrantes(evento_id: int) -> list[Atividade]:
    """
    Todas as atividades de um evento, com descrição, vagas e ministrantes,
    ordenadas pelo horário de início.

    Usa duas consultas (atividades e ministrantes do evento inteiro) em vez
    de uma por atividade.
    """
    atividades_query = text(
        """
        SELECT a.id_evento, a.id, a.nome, a.sala,
               a.data_hora_inicio, a.data_hora_fim, a.descricao, a.vagas
        FROM atividade a
        WHERE a.id_evento = :id_evento
        ORDER BY a.data_hora_inicio, a.id
        """
    )
    ministrantes_query = text(
        """
        SELECT m.id_usuario, m.id_evento, m.id_atividade,
               m.mini_bio, m.instituicao, m.link_lattes,
               v.id, v.nome, v.cpf::text, v.email, v.data_nascimento,
               v.papel, v.sexo::text, v.idade::int
        FROM ministra_atividade m
        JOIN usuario_com_idade v ON v.id = m.id_usuario
        WHERE m.id_evento = :id_evento
        ORDER BY v.nome
        """
    )
    params = {"id_evento": evento_id}
    with session_maker() as session:
        atividades = [
            Atividade.de_linha(row)
            for row in session.execute(atividades_query, params).mappings()
        ]
        por_id = {a.id: a for a in atividades}
        for row in session.execute(ministrantes_query, params).mappings():
            por_id[row["id_atividade"]].ministrantes.append(Ministrante.de_linha(row))
    return atividades
