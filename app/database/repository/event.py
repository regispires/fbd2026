"""
Operações sobre a entidade de evento.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.database import session_maker
from app.database.repository import ensure_timezone, parse_point
from app.database.repository.activity import ActivityInput
from app.exceptions import (
    DuplicateEventRegistration,
    EventHasDependencies,
    EventNotFound,
    EventWithoutActivity,
    InvalidActivitySchedule,
)


@dataclass
class Event:
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
        self._check_localizacao_pair()

    def _check_localizacao_pair(self) -> None:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError(
                "latitude e longitude precisam estar ambos definidos ou ambos nulos"
            )

    def update(
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
    ) -> None:
        """Atualiza o evento; o par latitude/longitude segue a regra ambos ou nenhum."""
        _require_lat_lng_pair(latitude, longitude)
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
                localizacao = CASE
                    WHEN :latitude IS NOT NULL AND :longitude IS NOT NULL
                    THEN POINT(:longitude, :latitude)
                    ELSE NULL
                END
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
                        "descricao": descricao,
                        "data_hora_inicio": ensure_timezone(data_hora_inicio),
                        "data_hora_fim": ensure_timezone(data_hora_fim),
                        "classificacao_indicativa": classificacao_indicativa,
                        "vagas": vagas,
                        "valor": valor,
                        "latitude": latitude,
                        "longitude": longitude,
                    },
                )
            except IntegrityError as e:
                raise DuplicateEventRegistration from e
            session.commit()

    def delete(self) -> bool:
        """
        Exclui o evento, retornando ``True`` se uma linha foi removida.

        A exclusão é bloqueada pelo banco (FK de ``atividade`` e
        ``inscricao_evento``) quando há dependências, o que é traduzido para
        ``EventHasDependencies``.
        """
        query = text("DELETE FROM evento WHERE id = :id RETURNING id")
        with session_maker() as session:
            session.begin()
            try:
                result = session.execute(query, {"id": self.id})
            except IntegrityError as e:
                raise EventHasDependencies from e
            session.commit()
            return result.rowcount == 1


def _require_lat_lng_pair(latitude: float | None, longitude: float | None) -> None:
    """O POINT é atômico: o par de coordenadas vem inteiro ou não vem."""
    if (latitude is None) != (longitude is None):
        raise ValueError(
            "latitude e longitude precisam estar ambos definidos ou ambos nulos"
        )


def _row_to_event(row: dict) -> Event:
    """Constrói um ``Event`` de uma linha, convertendo o POINT para floats."""
    longitude, latitude = parse_point(row.pop("localizacao"))
    return Event(latitude=latitude, longitude=longitude, **row)


@dataclass
class EventList:
    """Coleção de eventos para a interface."""

    items: list[Event]
    on_change: Callable

    def reload(self) -> None:
        query = text(
            """
            SELECT id, nome, descricao, data_hora_inicio, data_hora_fim,
                   classificacao_indicativa, vagas, valor, localizacao::text,
                   banner, banner_thumbnail,
                   (SELECT COUNT(i.id_usuario)
                    FROM inscricao_evento i
                    WHERE i.id_evento = evento.id
                      AND i.status <> 'cancelada') AS inscritas
            FROM evento
            ORDER BY data_hora_inicio
            """
        )
        with session_maker() as session:
            self.items = [
                _row_to_event(dict(row))
                for row in session.execute(query).mappings()
            ]
        self.on_change()


def get_event(event_id: int) -> Event:
    """
    Busca um evento por id; lança ``EventNotFound`` se não existir.

    Também preenche ``inscritas`` (inscrições não canceladas), usado pela
    página de detalhes para mostrar as vagas disponíveis.
    """
    query = text(
        """
        SELECT id, nome, descricao, data_hora_inicio, data_hora_fim,
               classificacao_indicativa, vagas, valor, localizacao::text,
               banner, banner_thumbnail,
               (SELECT COUNT(i.id_usuario)
                FROM inscricao_evento i
                WHERE i.id_evento = evento.id
                  AND i.status <> 'cancelada') AS inscritas
        FROM evento
        WHERE id = :event_id
        LIMIT 1
        """
    )
    with session_maker() as session:
        row = session.execute(query, {"event_id": event_id}).mappings().first()
    if row is None:
        raise EventNotFound
    return _row_to_event(dict(row))


@dataclass
class EventRaisedValue:
    """Linha agregada do valor das inscrições de um evento, por status."""

    status: str
    total: float


def get_event_raised_values(event_id: int) -> list[EventRaisedValue]:
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
        WHERE id_evento = :event_id
        GROUP BY status
        ORDER BY status
        """
    )
    with session_maker() as session:
        rows = session.execute(query, {"event_id": event_id}).mappings()
    return [
        EventRaisedValue(status=r["status"], total=float(r["total"])) for r in rows
    ]


def create_event(
    nome: str,
    descricao: str | None,
    data_hora_inicio: datetime,
    data_hora_fim: datetime,
    classificacao_indicativa: int | None,
    vagas: int,
    valor: float,
    latitude: float | None = None,
    longitude: float | None = None,
    activities: list[ActivityInput] | None = None,
    banner: str | None = None,
    banner_thumbnail: str | None = None,
) -> Event:
    """
    Cria um evento e suas atividades na mesma transação.

    Um evento precisa ter pelo menos uma atividade (regra de negócio);
    ``activities`` vazia ou ``None`` levanta ``EventWithoutActivity``. O
    horário de cada atividade deve estar contido no horário do evento
    (``InvalidActivitySchedule``).

    ``nome`` é único no banco (violação vira ``DuplicateEventRegistration``);
    os ids das atividades são gerados pelo banco. A localização é opcional,
    mas o par lat/lng deve vir inteiro ou não vir.
    """
    _require_lat_lng_pair(latitude, longitude)
    if not activities:
        raise EventWithoutActivity
    for activity in activities:
        if (
            ensure_timezone(activity.data_hora_inicio) < ensure_timezone(data_hora_inicio)
            or ensure_timezone(activity.data_hora_fim) > ensure_timezone(data_hora_fim)
        ):
            raise InvalidActivitySchedule

    event_query = text(
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
    activity_query = text(
        """
        INSERT INTO atividade
            (id_evento, nome, descricao, sala, vagas, data_hora_inicio, data_hora_fim)
        VALUES
            (:id_evento, :nome, :descricao, :sala, :vagas,
             :data_hora_inicio, :data_hora_fim)
        """
    )
    with session_maker() as session:
        session.begin()
        try:
            result = session.execute(
                event_query,
                {
                    "nome": nome,
                    "descricao": descricao,
                    "data_hora_inicio": ensure_timezone(data_hora_inicio),
                    "data_hora_fim": ensure_timezone(data_hora_fim),
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
            raise DuplicateEventRegistration from e
        # consome o RETURNING antes de executar as demais statements na
        # mesma conexão (o cursor não aceita outra query com resultado
        # pendente)
        event_row = dict(result.mappings().first())
        new_id: int = event_row["id"]
        for activity in activities:
            session.execute(
                activity_query,
                {
                    "id_evento": new_id,
                    "nome": activity.nome,
                    "descricao": activity.descricao,
                    "sala": activity.sala,
                    "vagas": activity.vagas,
                    "data_hora_inicio": ensure_timezone(activity.data_hora_inicio),
                    "data_hora_fim": ensure_timezone(activity.data_hora_fim),
                },
            )
        session.commit()
    return _row_to_event(event_row)
