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
    ActivityWithoutLecturer,
    DuplicateEventRegistration,
    DuplicateLecturer,
    EventHasDependencies,
    EventHasInscriptions,
    EventNotFound,
    EventWithoutActivity,
    InvalidActivitySchedule,
    InvalidEventSchedule,
    VacancyBelowInscriptions,
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
        banner: str | None = None,
        banner_thumbnail: str | None = None,
    ) -> None:
        """
        Atualiza o evento; o par latitude/longitude segue a regra ambos ou
        nenhum. Regras validadas na mesma transação da escrita:

        - o início precisa ser anterior ao fim (``InvalidEventSchedule``);
        - as vagas não podem ficar menores que o número de inscrições ativas
          (``VacancyBelowInscriptions``);
        - o novo intervalo de datas precisa continuar contendo todas as
          atividades existentes (``InvalidActivitySchedule``).

        ``banner`` e ``banner_thumbnail`` são URLs; ``None`` limpa a coluna.
        """
        _require_lat_lng_pair(latitude, longitude)
        _require_valid_schedule(data_hora_inicio, data_hora_fim)
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
        inicio = ensure_timezone(data_hora_inicio)
        fim = ensure_timezone(data_hora_fim)
        with session_maker() as session:
            session.begin()
            inscritas = session.execute(inscritas_query, {"id": self.id}).scalar_one()
            if vagas < inscritas:
                raise VacancyBelowInscriptions
            for atividade in session.execute(
                atividades_query, {"id": self.id}
            ).mappings():
                if (
                    atividade["data_hora_inicio"] < inicio
                    or atividade["data_hora_fim"] > fim
                ):
                    raise InvalidActivitySchedule
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
                raise DuplicateEventRegistration from e
            session.commit()

    def delete(self) -> bool:
        """
        Exclui o evento, retornando ``True`` se uma linha foi removida.

        A exclusão é bloqueada quando o evento possui ao menos uma inscrição
        (de qualquer status, ``EventHasInscriptions``). Sem inscrições, as
        dependências do evento (presenças, ministrantes e atividades) são
        removidas junto na mesma transação; uma violação de chave
        estrangeira — p.ex. uma inscrição criada entre a verificação e a
        exclusão — é traduzida para ``EventHasDependencies``.
        """
        count_query = text(
            """
            SELECT COUNT(i.id_usuario) AS total
            FROM inscricao_evento i
            WHERE i.id_evento = :id
            """
        )
        with session_maker() as session:
            inscritas = session.execute(count_query, {"id": self.id}).scalar_one()
        if inscritas > 0:
            raise EventHasInscriptions

        query = text("DELETE FROM evento WHERE id = :id RETURNING id")
        with session_maker() as session:
            session.begin()
            try:
                # ordem importa: presença e ministrantes referenciam
                # atividades, que referenciam o evento
                for table in ("presenca_atividade", "ministra_atividade", "atividade"):
                    _ = session.execute(
                        text(f"DELETE FROM {table} WHERE id_evento = :id"),
                        {"id": self.id},
                    )
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


def _require_valid_schedule(
    data_hora_inicio: datetime, data_hora_fim: datetime
) -> None:
    """O horário do evento precisa ter início anterior ao fim."""
    if ensure_timezone(data_hora_inicio) >= ensure_timezone(data_hora_fim):
        raise InvalidEventSchedule


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
                _row_to_event(dict(row)) for row in session.execute(query).mappings()
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
    return [EventRaisedValue(status=r["status"], total=float(r["total"])) for r in rows]


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
    (``InvalidActivitySchedule``) e cada atividade precisa de ao menos um
    ministrante (``ActivityWithoutLecturer``); os vínculos de ministrantes
    são criados na mesma transação.

    ``nome`` é único no banco (violação vira ``DuplicateEventRegistration``);
    os ids das atividades são gerados pelo banco. A localização é opcional,
    mas o par lat/lng deve vir inteiro ou não vir. O horário precisa ter
    início anterior ao fim (``InvalidEventSchedule``) e o evento precisa de
    pelo menos uma vaga.
    """
    _require_lat_lng_pair(latitude, longitude)
    _require_valid_schedule(data_hora_inicio, data_hora_fim)
    if vagas < 1:
        raise ValueError("o evento precisa de pelo menos uma vaga")
    if not activities:
        raise EventWithoutActivity
    if any(not activity.lecturers for activity in activities):
        raise ActivityWithoutLecturer
    for activity in activities:
        if ensure_timezone(activity.data_hora_inicio) < ensure_timezone(
            data_hora_inicio
        ) or ensure_timezone(activity.data_hora_fim) > ensure_timezone(data_hora_fim):
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
        RETURNING id
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
            activity_result = session.execute(
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
            # consome o RETURNING antes de executar as demais statements na
            # mesma conexão (o cursor não aceita outra query com resultado
            # pendente)
            activity_id: int = activity_result.scalar_one()
            for entry in activity.lecturers:
                try:
                    _ = session.execute(
                        lecturer_query,
                        {
                            "id_usuario": entry.user.id,
                            "id_evento": new_id,
                            "id_atividade": activity_id,
                            "mini_bio": entry.mini_bio,
                            "instituicao": entry.instituicao,
                            "link_lattes": entry.link_lattes,
                        },
                    )
                except IntegrityError as e:
                    raise DuplicateLecturer from e
        session.commit()
    return _row_to_event(event_row)
