"""
Consultas agregadas do dashboard de estatísticas (``/event/dashboard``).

Todas as estatísticas são calculadas no banco com ``GROUP BY``/``FILTER``:
a aplicação recebe apenas linhas já agregadas (uma por evento, ou uma por
grupo demográfico), nunca a lista de inscrições ou de participantes.

O escopo é um evento (``evento_id``) ou todos os eventos (``None``). Na
visão global, cada inscrição conta uma vez: quem se inscreveu em dois
eventos aparece nas estatísticas de cada um deles.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import text

from app.database import session_maker

# faixas etárias da demografia: índice calculado no SQL -> rótulo
FAIXAS_ETARIAS = ["Até 17", "18–24", "25–34", "35–44", "45–59", "60+"]

# status considerados na demografia (seletor da página)
STATUS_CONFIRMADAS = ("confirmada",)
STATUS_ATIVAS = ("confirmada", "pendente")


@dataclass
class OpcaoEvento:
    """Evento no seletor do dashboard (apenas id e nome)."""

    id: int
    nome: str


def listar_opcoes_eventos() -> list[OpcaoEvento]:
    """Todos os eventos para o seletor, dos mais recentes aos mais antigos."""
    query = text(
        """
        SELECT id, nome
        FROM evento
        ORDER BY data_hora_inicio DESC, id DESC
        """
    )
    with session_maker() as session:
        rows = session.execute(query).mappings()
        return [OpcaoEvento(id=row["id"], nome=row["nome"]) for row in rows]


@dataclass
class ResumoEvento:
    """
    Contagens e valores das inscrições de um evento, agregados no banco.

    Os campos são aditivos, então o resumo global é a soma dos resumos
    dos eventos (``somar_resumos``); os indicadores derivados (ocupação,
    ticket médio, ...) são propriedades calculadas a partir deles.
    """

    id: int | None
    nome: str
    vagas: int
    valor: float  # preço cheio (0 no resumo global)
    data_hora_inicio: datetime | None
    data_hora_fim: datetime | None
    confirmadas: int
    pendentes: int
    canceladas: int
    receita_confirmada: float
    receita_pendente: float
    receita_cancelada: float
    receita_potencial: float  # vagas x preço cheio
    meias_confirmadas: int
    receita_meia: float  # arrecadado com as meias confirmadas
    desconto_meia: float  # (preço cheio - valor pago) das meias confirmadas
    sem_comprovante: int  # inscrições ativas de evento pago sem comprovante
    eventos: int = 1

    @property
    def total(self) -> int:
        return self.confirmadas + self.pendentes + self.canceladas

    @property
    def ativas(self) -> int:
        """Inscrições que ocupam vaga (as não canceladas)."""
        return self.confirmadas + self.pendentes

    @property
    def ocupacao(self) -> float:
        return self.ativas / self.vagas if self.vagas else 0.0

    @property
    def taxa_cancelamento(self) -> float:
        return self.canceladas / self.total if self.total else 0.0

    @property
    def inteiras_confirmadas(self) -> int:
        return self.confirmadas - self.meias_confirmadas

    @property
    def receita_inteira(self) -> float:
        return self.receita_confirmada - self.receita_meia

    @property
    def ticket_medio(self) -> float:
        return self.receita_confirmada / self.confirmadas if self.confirmadas else 0.0


@dataclass
class SituacaoEventos:
    """Quantos eventos do escopo ainda vão começar, estão ocorrendo ou acabaram."""

    futuros: int = 0
    em_andamento: int = 0
    encerrados: int = 0


def resumir_eventos(evento_id: int | None = None) -> list[ResumoEvento]:
    """
    Um ``ResumoEvento`` por evento do escopo (todos, se ``evento_id`` for
    ``None``), ordenados pelo início mais recente.

    As inscrições são agregadas por evento com ``COUNT``/``SUM ... FILTER``
    em uma única leitura de ``inscricao_evento``. O ``LEFT JOIN`` mantém os
    eventos sem inscrições (todas as contagens zeradas).
    """
    query = text(
        """
        SELECT e.id, e.nome, e.vagas, e.valor,
               e.data_hora_inicio, e.data_hora_fim,
               COUNT(i.id_usuario) FILTER (WHERE i.status = 'confirmada') AS confirmadas,
               COUNT(i.id_usuario) FILTER (WHERE i.status = 'pendente') AS pendentes,
               COUNT(i.id_usuario) FILTER (WHERE i.status = 'cancelada') AS canceladas,
               COALESCE(SUM(i.valor) FILTER (WHERE i.status = 'confirmada'), 0)
                   AS receita_confirmada,
               COALESCE(SUM(i.valor) FILTER (WHERE i.status = 'pendente'), 0)
                   AS receita_pendente,
               COALESCE(SUM(i.valor) FILTER (WHERE i.status = 'cancelada'), 0)
                   AS receita_cancelada,
               e.vagas * e.valor AS receita_potencial,
               COUNT(i.id_usuario) FILTER (WHERE i.status = 'confirmada' AND i.meia)
                   AS meias_confirmadas,
               COALESCE(SUM(i.valor) FILTER (WHERE i.status = 'confirmada' AND i.meia), 0)
                   AS receita_meia,
               COALESCE(SUM(e.valor - i.valor)
                        FILTER (WHERE i.status = 'confirmada' AND i.meia), 0)
                   AS desconto_meia,
               COUNT(i.id_usuario) FILTER (
                   WHERE e.valor > 0
                     AND i.status <> 'cancelada'
                     AND i.comprovante_usuario IS NULL
               ) AS sem_comprovante
        FROM evento e
        LEFT JOIN inscricao_evento i ON i.id_evento = e.id
        WHERE CAST(:evento_id AS INTEGER) IS NULL OR e.id = :evento_id
        GROUP BY e.id
        ORDER BY e.data_hora_inicio DESC, e.id DESC
        """
    )
    with session_maker() as session:
        rows = session.execute(query, {"evento_id": evento_id}).mappings()
        return [ResumoEvento(**row) for row in rows]


def somar_resumos(resumos: Sequence[ResumoEvento]) -> ResumoEvento:
    """
    Resumo global: soma dos resumos (já agregados no banco) de cada evento.

    Os campos somados são aditivos; o preço e as datas não se aplicam a
    vários eventos e ficam zerados/``None``.
    """
    return ResumoEvento(
        id=None,
        nome="Todos os eventos",
        vagas=sum(r.vagas for r in resumos),
        valor=0.0,
        data_hora_inicio=None,
        data_hora_fim=None,
        confirmadas=sum(r.confirmadas for r in resumos),
        pendentes=sum(r.pendentes for r in resumos),
        canceladas=sum(r.canceladas for r in resumos),
        receita_confirmada=sum(r.receita_confirmada for r in resumos),
        receita_pendente=sum(r.receita_pendente for r in resumos),
        receita_cancelada=sum(r.receita_cancelada for r in resumos),
        receita_potencial=sum(r.receita_potencial for r in resumos),
        meias_confirmadas=sum(r.meias_confirmadas for r in resumos),
        receita_meia=sum(r.receita_meia for r in resumos),
        desconto_meia=sum(r.desconto_meia for r in resumos),
        sem_comprovante=sum(r.sem_comprovante for r in resumos),
        eventos=len(resumos),
    )


def situacao_eventos(resumos: Sequence[ResumoEvento], agora: datetime) -> SituacaoEventos:
    """Classifica os eventos do escopo em futuros, em andamento e encerrados."""
    situacao = SituacaoEventos()
    for r in resumos:
        if r.data_hora_inicio is None or r.data_hora_fim is None:
            continue
        if agora < r.data_hora_inicio:
            situacao.futuros += 1
        elif agora <= r.data_hora_fim:
            situacao.em_andamento += 1
        else:
            situacao.encerrados += 1
    return situacao


@dataclass
class Demografia:
    """
    Perfil dos participantes (inscrições) do escopo.

    As contagens são indexadas pelo código da coluna (``sexo``,
    ``estado_civil``) e pelo índice da faixa etária em ``FAIXAS_ETARIAS``.
    """

    total: int = 0
    idade_media: float | None = None
    idade_minima: int | None = None
    idade_maxima: int | None = None
    # (faixa, sexo) -> quantidade
    faixa_sexo: dict[tuple[int, str], int] = field(default_factory=dict)
    # (faixa, meia) -> quantidade
    faixa_meia: dict[tuple[int, bool], int] = field(default_factory=dict)
    # estado civil -> quantidade
    estado_civil: dict[str, int] = field(default_factory=dict)

    def por_faixa(self) -> list[int]:
        """Quantidade em cada faixa etária, na ordem de ``FAIXAS_ETARIAS``."""
        totais = [0] * len(FAIXAS_ETARIAS)
        for (faixa, _), quantidade in self.faixa_sexo.items():
            totais[faixa] += quantidade
        return totais

    def por_sexo(self) -> dict[str, int]:
        totais: dict[str, int] = {}
        for (_, sexo), quantidade in self.faixa_sexo.items():
            totais[sexo] = totais.get(sexo, 0) + quantidade
        return totais


def obter_demografia(
    evento_id: int | None = None, status: Sequence[str] = STATUS_CONFIRMADAS
) -> Demografia:
    """
    Demografia das inscrições do escopo com os ``status`` informados.

    A idade é calculada **na data de início do evento** (e não hoje), para
    que eventos passados mostrem a idade que os participantes tinham.

    Uma única consulta com ``GROUPING SETS`` agrega os participantes de
    quatro formas de uma só vez; ``GROUPING(...)`` devolve uma máscara de
    bits indicando quais colunas foram agregadas na linha (bit ligado =
    coluna agregada, na ordem faixa=8, sexo=4, estado_civil=2, meia=1):

    - ``()`` -> 15: total, idade média, mínima e máxima;
    - ``(faixa, sexo)`` -> 3: pirâmide etária (e os totais por faixa e sexo);
    - ``(faixa, meia)`` -> 6: meia-entrada por faixa etária;
    - ``(estado_civil)`` -> 13: estado civil.
    """
    query = text(
        """
        WITH participantes AS (
            SELECT u.sexo::text AS sexo,
                   u.estado_civil::text AS estado_civil,
                   i.meia,
                   EXTRACT(YEAR FROM AGE(e.data_hora_inicio::date, u.data_nascimento))::int
                       AS idade
            FROM inscricao_evento i
            JOIN evento e ON e.id = i.id_evento
            JOIN usuario u ON u.id = i.id_usuario
            WHERE (CAST(:evento_id AS INTEGER) IS NULL OR i.id_evento = :evento_id)
              AND i.status::text = ANY(:status)
        ),
        com_faixa AS (
            SELECT sexo, estado_civil, meia, idade,
                   CASE
                       WHEN idade < 18 THEN 0
                       WHEN idade < 25 THEN 1
                       WHEN idade < 35 THEN 2
                       WHEN idade < 45 THEN 3
                       WHEN idade < 60 THEN 4
                       ELSE 5
                   END AS faixa
            FROM participantes
        )
        SELECT GROUPING(faixa, sexo, estado_civil, meia) AS conjunto,
               faixa, sexo, estado_civil, meia,
               COUNT(*) AS quantidade,
               AVG(idade)::float AS idade_media,
               MIN(idade) AS idade_minima,
               MAX(idade) AS idade_maxima
        FROM com_faixa
        GROUP BY GROUPING SETS ((), (faixa, sexo), (faixa, meia), (estado_civil))
        """
    )
    params = {"evento_id": evento_id, "status": list(status)}
    with session_maker() as session:
        rows = session.execute(query, params).mappings().all()

    demografia = Demografia()
    for row in rows:
        match row["conjunto"]:
            case 15:
                demografia.total = row["quantidade"]
                demografia.idade_media = row["idade_media"]
                demografia.idade_minima = row["idade_minima"]
                demografia.idade_maxima = row["idade_maxima"]
            case 3:
                demografia.faixa_sexo[(row["faixa"], row["sexo"])] = row["quantidade"]
            case 6:
                demografia.faixa_meia[(row["faixa"], row["meia"])] = row["quantidade"]
            case 13:
                demografia.estado_civil[row["estado_civil"]] = row["quantidade"]
    return demografia
