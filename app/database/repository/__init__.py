"""
Esse módulo possui as operações sobre as entidades da aplicação,
representadas por dataclasses com colunas explícitas.

Todas as queries são construídas com SQL parametrizado (text), sem usar o
ORM. Modificações usam transações explícitas: session.begin e session.commit(),
de modo que erros rolem a transação de volta ao fechar a sessão.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.database.settings import settings

# o pacote tzdata fornece a base de fusos (ausente na imagem alpine)
FUSO_EVENTOS = ZoneInfo(settings.DATABASE_TIMEZONE)


def ensure_timezone(dt: datetime) -> datetime:
    """
    Garante que um ``datetime`` chegue ao banco com timezone.

    O banco armazena ``TIMESTAMPTZ``; datetimes sem timezone (ex.: vindos de
    formulários) são assumidos no fuso dos eventos (``DATABASE_TIMEZONE``).
    """
    return dt.replace(tzinfo=FUSO_EVENTOS) if dt.tzinfo is None else dt


def as_bytes(value: memoryview | None) -> bytes | None:
    """psycopg2 retorna ``BYTEA`` como ``memoryview``; converte para ``bytes``."""
    return bytes(value) if value is not None else None


def parse_point(localizacao: str | None) -> tuple[float | None, float | None]:
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
