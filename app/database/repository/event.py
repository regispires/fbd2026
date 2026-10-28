"""
Operações sobre a entidade de evento.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.database import session_maker
from app.database.repository import (
    analisar_ponto,
    contar_linhas,
    contido_em,
    garantir_timezone,
)
from app.database.repository.activity import EntradaAtividade
from app.exceptions import (
    AtividadeSemMinistrante,
    EventoComDependencias,
    EventoComInscricoes,
    EventoNaoEncontrado,
    EventoRepetido,
    EventoSemAtividade,
    HorarioAtividadeInvalido,
    HorarioEventoInvalido,
    MinistranteRepetido,
    VagasAbaixoInscricoes,
)

# colunas + contagem de inscrições ativas, compartilhadas pelas consultas
# de listagem e de detalhe
_COLUNAS_EVENTO = """
    SELECT id, nome, descricao, data_hora_inicio, data_hora_fim,
           classificacao_indicativa, vagas, valor, localizacao::text,
           banner, banner_thumbnail,
           (SELECT COUNT(i.id_usuario)
            FROM inscricao_evento i
            WHERE i.id_evento = evento.id
              AND i.status <> 'cancelada') AS inscritas
    FROM evento
"""


@dataclass
class Evento:
    """
    Representa a tabela ``evento``.

    ``localizacao`` (POINT) é projetada como ``latitude``/``longitude``: o
    par é atômico no banco, então os dois valores vêm juntos (ambos
    ``None`` ou ambos definidos).
    """

    id: int
    nome: str
    descricao: str | None
    data_hora_inicio: datetime
    data_hora_fim: datetime
    classificacao_indicativa: int | None  # None = sem restrição de idade
    vagas: int
    latitude: float | None
    longitude: float | None
    # URLs das imagens do evento (opcionais): banner em tamanho cheio e a
    # versão reduzida usada nas listagens
    banner: str | None = None
    banner_thumbnail: str | None = None
    # preço cheio do evento
    valor: float = 0.0
    # Contagem de inscrições ativas (não canceladas); preenchida apenas pela
    # listagem de eventos, para a interface sinalizar eventos sem vagas.
    inscritas: int | None = None

    def __post_init__(self) -> None:
        _exigir_par_lat_lng(self.latitude, self.longitude)

    @classmethod
    def de_linha(cls, row: Mapping[str, Any]) -> "Evento":
        """Constrói um ``Evento`` de uma linha, convertendo o POINT para floats."""
        row = dict(row)
        longitude, latitude = analisar_ponto(row.pop("localizacao"))
        return cls(latitude=latitude, longitude=longitude, **row)

    @property
    def valor_meia(self) -> float:
        """Preço da meia-entrada (regra: metade do valor cheio)."""
        return round(self.valor / 2, 2)

    def atualizar(
        self,
        nome: str,
        descricao: str | None,
        data_hora_inicio: datetime,
        data_hora_fim: datetime,
        classificacao_indicativa: int | None,
        vagas: int,
        latitude: float | None,
        longitude: float | None,
        valor: float,
        banner: str | None = None,
        banner_thumbnail: str | None = None,
    ) -> None:
        """
        Atualiza o evento; o par latitude/longitude segue a regra ambos ou
        nenhum. Regras validadas na mesma transação da escrita:

        - o início precisa ser anterior ao fim (``HorarioEventoInvalido``);
        - as vagas não podem ficar menores que o número de inscrições ativas
          (``VagasAbaixoInscricoes``);
        - o novo intervalo de datas precisa continuar contendo todas as
          atividades existentes (``HorarioAtividadeInvalido``).

        ``banner`` e ``banner_thumbnail`` são URLs; ``None`` limpa a coluna.
        """
        _exigir_par_lat_lng(latitude, longitude)
        _exigir_horario_valido(data_hora_inicio, data_hora_fim)
        if vagas < 1:
            raise ValueError("o evento precisa de pelo menos uma vaga")

        inscritas_query = text(
            """
            SELECT COUNT(i.id_usuario) AS total
            FROM inscricao_evento i
            WHERE i.id_evento = :id
              AND i.status <> 'cancelada'
            """
        )
        atividades_query = text(
            """
            SELECT data_hora_inicio, data_hora_fim
            FROM atividade
            WHERE id_evento = :id
            """
        )
        query = text(
            """
            UPDATE evento
            SET nome = :nome,
                descricao = :descricao,
                data_hora_inicio = :data_hora_inicio,
                data_hora_fim = :data_hora_fim,
                classificacao_indicativa = :classificacao_indicativa,
                vagas = :vagas,
                valor = :valor,
                banner = :banner,
                banner_thumbnail = :banner_thumbnail,
                localizacao = CASE
                    WHEN :latitude IS NOT NULL AND :longitude IS NOT NULL
                    THEN POINT(:longitude, :latitude)
                    ELSE NULL
                END
            WHERE id = :id
            """
        )
        inicio = garantir_timezone(data_hora_inicio)
        fim = garantir_timezone(data_hora_fim)
        with session_maker() as session:
            session.begin()
            inscritas = session.execute(inscritas_query, {"id": self.id}).scalar_one()
            if vagas < inscritas:
                raise VagasAbaixoInscricoes
            for atividade in session.execute(
                atividades_query, {"id": self.id}
            ).mappings():
                if not contido_em(
                    atividade["data_hora_inicio"],
                    atividade["data_hora_fim"],
                    inicio,
                    fim,
                ):
                    raise HorarioAtividadeInvalido
            try:
                _ = session.execute(
                    query,
                    {
                        "id": self.id,
                        "nome": nome,
                        "descricao": descricao,
                        "data_hora_inicio": inicio,
                        "data_hora_fim": fim,
                        "classificacao_indicativa": classificacao_indicativa,
                        "vagas": vagas,
                        "valor": valor,
                        "banner": banner,
                        "banner_thumbnail": banner_thumbnail,
                        "latitude": latitude,
                        "longitude": longitude,
                    },
                )
            except IntegrityError as e:
                raise EventoRepetido from e
            session.commit()

    def excluir(self) -> bool:
        """
        Exclui o evento, retornando ``True`` se uma linha foi removida.

        A exclusão é bloqueada quando o evento possui ao menos uma inscrição
        (de qualquer status, ``EventoComInscricoes``). Sem inscrições, as
        dependências do evento (presenças, ministrantes e atividades) são
        removidas junto na mesma transação; uma violação de chave
        estrangeira — p.ex. uma inscrição criada entre a verificação e a
        exclusão — é traduzida para ``EventoComDependencias``.
        """
        inscritas = contar_linhas(
            """
            SELECT COUNT(i.id_usuario) AS total
            FROM inscricao_evento i
            WHERE i.id_evento = :id
            """,
            {"id": self.id},
        )
        if inscritas > 0:
            raise EventoComInscricoes

        query = text("DELETE FROM evento WHERE id = :id RETURNING id")
        with session_maker() as session:
            session.begin()
            try:
                # ordem importa: presença e ministrantes referenciam
                # atividades, que referenciam o evento
                for tabela in ("presenca_atividade", "ministra_atividade", "atividade"):
                    _ = session.execute(
                        text(f"DELETE FROM {tabela} WHERE id_evento = :id"),
                        {"id": self.id},
                    )
                result = session.execute(query, {"id": self.id})
            except IntegrityError as e:
                raise EventoComDependencias from e
            session.commit()
            return result.rowcount == 1


def _exigir_par_lat_lng(latitude: float | None, longitude: float | None) -> None:
    """O POINT é atômico: o par de coordenadas vem inteiro ou não vem."""
    if (latitude is None) != (longitude is None):
        raise ValueError(
            "latitude e longitude precisam estar ambos definidos ou ambos nulos"
        )


def _exigir_horario_valido(data_hora_inicio: datetime, data_hora_fim: datetime) -> None:
    """O horário do evento precisa ter início anterior ao fim."""
    if garantir_timezone(data_hora_inicio) >= garantir_timezone(data_hora_fim):
        raise HorarioEventoInvalido


def listar_eventos() -> list[Evento]:
    """Todos os eventos, ordenados pelo início (cartões da página inicial)."""
    query = text(f"{_COLUNAS_EVENTO} ORDER BY data_hora_inicio")
    with session_maker() as session:
        rows = session.execute(query).mappings()
    return [Evento.de_linha(row) for row in rows]


def obter_evento(evento_id: int) -> Evento:
    """
    Busca um evento por id; lança ``EventoNaoEncontrado`` se não existir.

    Também preenche ``inscritas`` (inscrições não canceladas), usado pela
    página de detalhes para mostrar as vagas disponíveis.
    """
    query = text(f"{_COLUNAS_EVENTO} WHERE id = :evento_id LIMIT 1")
    with session_maker() as session:
        row = session.execute(query, {"evento_id": evento_id}).mappings().first()
    if row is None:
        raise EventoNaoEncontrado
    return Evento.de_linha(row)


@dataclass
class ValorArrecadado:
    """Linha agregada do valor das inscrições de um evento, por status."""

    status: str
    total: float


def obter_valores_arrecadados(evento_id: int) -> list[ValorArrecadado]:
    """
    Valor das inscrições de um evento agrupado por status (regra de
    negócio para o detalhamento administrativo em ``/events/{id}``):

    - ``confirmada``: valor arrecadado;
    - ``pendente``: valor a arrecadar;
    - ``cancelada``: valor deixado de arrecadar.

    Retorna apenas os status presentes no evento; ``COALESCE`` zera a soma
    quando inscrições do status não têm valor informado.
    """
    query = text(
        """
        SELECT status, COALESCE(SUM(valor), 0) AS total
        FROM inscricao_evento
        WHERE id_evento = :evento_id
        GROUP BY status
        ORDER BY status
        """
    )
    with session_maker() as session:
        rows = session.execute(query, {"evento_id": evento_id}).mappings()
    return [ValorArrecadado(status=r["status"], total=float(r["total"])) for r in rows]


def criar_evento(
    nome: str,
    descricao: str | None,
    data_hora_inicio: datetime,
    data_hora_fim: datetime,
    classificacao_indicativa: int | None,
    vagas: int,
    valor: float,
    latitude: float | None = None,
    longitude: float | None = None,
    atividades: list[EntradaAtividade] | None = None,
    banner: str | None = None,
    banner_thumbnail: str | None = None,
) -> Evento:
    """
    Cria um evento e suas atividades na mesma transação.

    Um evento precisa ter pelo menos uma atividade (regra de negócio);
    ``atividades`` vazia ou ``None`` levanta ``EventoSemAtividade``. O
    horário de cada atividade deve estar contido no horário do evento
    (``HorarioAtividadeInvalido``) e cada atividade precisa de ao menos um
    ministrante (``AtividadeSemMinistrante``); os vínculos de ministrantes
    são criados na mesma transação.

    ``nome`` é único no banco (violação vira ``EventoRepetido``);
    os ids das atividades são gerados pelo banco. A localização é opcional,
    mas o par lat/lng deve vir inteiro ou não vir. O horário precisa ter
    início anterior ao fim (``HorarioEventoInvalido``) e o evento precisa de
    pelo menos uma vaga.
    """
    _exigir_par_lat_lng(latitude, longitude)
    _exigir_horario_valido(data_hora_inicio, data_hora_fim)
    if vagas < 1:
        raise ValueError("o evento precisa de pelo menos uma vaga")
    if not atividades:
        raise EventoSemAtividade
    if any(not entrada.ministrantes for entrada in atividades):
        raise AtividadeSemMinistrante
    for entrada in atividades:
        if not contido_em(
            entrada.data_hora_inicio,
            entrada.data_hora_fim,
            data_hora_inicio,
            data_hora_fim,
        ):
            raise HorarioAtividadeInvalido

    evento_query = text(
        """
        INSERT INTO evento
            (nome, descricao, data_hora_inicio, data_hora_fim,
             classificacao_indicativa, vagas, valor, localizacao, banner, banner_thumbnail)
        VALUES
            (:nome, :descricao, :data_hora_inicio, :data_hora_fim,
             :classificacao_indicativa, :vagas, :valor,
             CASE
                 WHEN :latitude IS NOT NULL AND :longitude IS NOT NULL
                 THEN POINT(:longitude, :latitude)
                 ELSE NULL
             END,
             :banner, :banner_thumbnail)
        RETURNING id, nome, descricao, data_hora_inicio, data_hora_fim,
                  classificacao_indicativa, vagas, valor, localizacao::text,
                  banner, banner_thumbnail
        """
    )
    atividade_query = text(
        """
        INSERT INTO atividade
            (id_evento, nome, descricao, sala, vagas, data_hora_inicio, data_hora_fim)
        VALUES
            (:id_evento, :nome, :descricao, :sala, :vagas,
             :data_hora_inicio, :data_hora_fim)
        RETURNING id
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
        try:
            result = session.execute(
                evento_query,
                {
                    "nome": nome,
                    "descricao": descricao,
                    "data_hora_inicio": garantir_timezone(data_hora_inicio),
                    "data_hora_fim": garantir_timezone(data_hora_fim),
                    "classificacao_indicativa": classificacao_indicativa,
                    "vagas": vagas,
                    "valor": valor,
                    "latitude": latitude,
                    "longitude": longitude,
                    "banner": banner,
                    "banner_thumbnail": banner_thumbnail,
                },
            )
        except IntegrityError as e:
            raise EventoRepetido from e
        # consome o RETURNING antes de executar as demais statements na
        # mesma conexão (o cursor não aceita outra query com resultado
        # pendente)
        evento_row = dict(result.mappings().first())
        novo_id: int = evento_row["id"]
        for entrada in atividades:
            params = {"id_evento": novo_id, **entrada.parametros()}
            params["data_hora_inicio"] = garantir_timezone(entrada.data_hora_inicio)
            params["data_hora_fim"] = garantir_timezone(entrada.data_hora_fim)
            atividade_result = session.execute(atividade_query, params)
            # consome o RETURNING antes de executar as demais statements na
            # mesma conexão (o cursor não aceita outra query com resultado
            # pendente)
            atividade_id: int = atividade_result.scalar_one()
            for ministrante in entrada.ministrantes:
                try:
                    _ = session.execute(
                        ministrante_query,
                        {
                            "id_usuario": ministrante.usuario.id,
                            "id_evento": novo_id,
                            "id_atividade": atividade_id,
                            "mini_bio": ministrante.mini_bio,
                            "instituicao": ministrante.instituicao,
                            "link_lattes": ministrante.link_lattes,
                        },
                    )
                except IntegrityError as e:
                    raise MinistranteRepetido from e
        session.commit()
    return Evento.de_linha(evento_row)
