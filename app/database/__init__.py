from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .settings import settings

engine = create_engine(settings.DATABASE_URI.get_secret_value())

session_maker = sessionmaker(engine)
