import os
from collections.abc import Iterator

from sqlalchemy import CheckConstraint, String, Text, create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class Todo(Base):
    __tablename__ = "todos"
    __table_args__ = (
        CheckConstraint("status IN ('planned', 'in_progress', 'done')"),
        CheckConstraint("priority IN ('low', 'medium', 'high')"),
        CheckConstraint("tag IS NULL OR tag IN ('hangout', 'work', 'important', 'trip')"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    # The API accepts date-only values and local datetimes without a timezone.
    start_at: Mapped[str] = mapped_column(String(19))
    end_at: Mapped[str] = mapped_column(String(19))
    location: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="planned")
    tag: Mapped[str | None] = mapped_column(String(20))
    priority: Mapped[str] = mapped_column(String(10), default="medium")
    assignee: Mapped[str] = mapped_column(Text, default="")


def database_url() -> URL:
    value = os.environ.get("DATABASE_URL")
    if value:
        url = make_url(value)
        if url.drivername in ("postgres", "postgresql"):
            url = url.set(drivername="postgresql+psycopg")
        return url
    return URL.create(
        "postgresql+psycopg",
        username=os.environ.get("POSTGRES_USER", "todos"),
        password=os.environ.get("POSTGRES_PASSWORD", ""),
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ.get("POSTGRES_DB", "todos"),
    )


engine = create_engine(database_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
