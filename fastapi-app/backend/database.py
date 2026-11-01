import os
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import CheckConstraint, DateTime, String, Text, create_engine, inspect
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
    # 시간대 없는 로컬 일시. 날짜만 받은 값은 API에서 시작은 0시, 종료는 23:59:59로 바꿔 저장한다.
    start_at: Mapped[datetime] = mapped_column(DateTime)
    end_at: Mapped[datetime] = mapped_column(DateTime)
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


MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
BASELINE_REVISION = "0001"   # Alembic 도입 전 create_all 로 만들던 스키마


def alembic_config() -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    return config


def init_db() -> None:
    """DB 스키마를 최신 마이그레이션까지 올린다."""
    config = alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection   # env.py 가 이 연결(테스트용 엔진 포함)을 그대로 사용
        tables = inspect(connection).get_table_names()
        if "todos" in tables and "alembic_version" not in tables:
            command.stamp(config, BASELINE_REVISION)   # 기존 DB는 기준 버전으로 표시만 하고 이어서 업그레이드
        command.upgrade(config, "head")


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
