from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from reflex.config import settings


class Base(DeclarativeBase):
    pass


writer_engine = create_engine(settings.database_url, pool_pre_ping=True)
readonly_engine = create_engine(settings.readonly_database_url, pool_pre_ping=True)

WriterSession = sessionmaker(bind=writer_engine)


def get_writer_session() -> Session:
    return WriterSession()
