"""
Esse módulo possui as operações sobre as entidades da aplicação,
representadas por dataclasses com colunas explícitas.

Todas as queries são construídas com SQL parametrizado (text), sem usar o
ORM. Modificações usam transações explícitas: session.begin e session.commit(),
de modo que erros rolem a transação de volta ao fechar a sessão.

Também concentra os utilitários compartilhados pelos módulos de repositório:
conversões de tipos do banco e verificações usadas por mais de um módulo.
"""

from collections.abc import Mapping
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.database import session_maker
from app.database.settings import settings

# o pacote tzdata fornece a base de fusos (ausente na imagem alpine)
FUSO_EVENTOS = ZoneInfo(settings.DATABASE_TIMEZONE)


def garantir_timezone(dt: datetime) -> datetime:
    """
    Garante que um ``datetime`` chegue ao banco com timezone.

    O banco armazena ``TIMESTAMPTZ``; datetimes sem timezone (ex.: vindos de
    formulários) são assumidos no fuso dos eventos (``DATABASE_TIMEZONE``).
    """
    return dt.replace(tzinfo=FUSO_EVENTOS) if dt.tzinfo is None else dt


def para_bytes(valor: memoryview | None) -> bytes | None:
    """psycopg2 retorna ``BYTEA`` como ``memoryview``; converte para ``bytes``."""
    return bytes(valor) if valor is not None else None


def eh_pdf(dados: bytes) -> bool:
    """
    Verifica o cabeçalho PDF (``%PDF``) no início dos bytes.

    Usado para validar o comprovante enviado: o filtro ``accept`` do
    uploader é apenas no cliente, então a validação definitiva fica aqui.
    """
    return dados[:4] == b"%PDF"


def analisar_ponto(localizacao: str | None) -> tuple[float | None, float | None]:
    """
    Converte o texto de um ``POINT`` (formato ``"(lon,lat)"``) em
    ``(longitude, latitude)``.

    ``None`` (localização inexistente) vira ``(None, None)``; o par é
    atômico, então nunca retorna apenas um dos dois valores.
    """
    if localizacao is None:
        return None, None
    lon_s, lat_s = localizacao.strip("()").split(",")
    return float(lon_s), float(lat_s)


def contido_em(
    inicio: datetime, fim: datetime, limite_inicio: datetime, limite_fim: datetime
) -> bool:
    """
    Verifica se o intervalo ``[inicio, fim]`` está contido em
    ``[limite_inicio, limite_fim]`` — a regra "o horário da atividade precisa
    estar contido no do evento", aplicada nas escritas e nas validações dos
    formulários. Datas sem timezone são assumidas no fuso dos eventos.
    """
    return garantir_timezone(inicio) >= garantir_timezone(limite_inicio) and (
        garantir_timezone(fim) <= garantir_timezone(limite_fim)
    )


def contar_linhas(sql: str, params: Mapping[str, Any] | None = None) -> int:
    """
    Executa uma consulta de contagem (coluna ``total``) e devolve o número.

    Usado nas verificações de vagas/presenças feitas fora da transação da
    escrita; contagens que precisam da mesma transação da escrita executam
    a query direto na ``session`` do chamador.
    """
    with session_maker() as session:
        row = session.execute(text(sql), dict(params or {})).mappings().first()
    return int(row["total"]) if row else 0
