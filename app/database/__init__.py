from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .settings import settings

engine = create_engine(
    settings.DATABASE_URI.get_secret_value(),
    # descarta conexões ociosas que o servidor já encerrou, evitando erros
    # de conexão em pool após reinícios ou quedas de rede
    pool_pre_ping=True,
    connect_args={"options": f"-c timezone={settings.DATABASE_TIMEZONE}"},
)

session_maker = sessionmaker(engine)
