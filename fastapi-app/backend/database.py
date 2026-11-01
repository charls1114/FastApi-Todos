import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, MetaData, String, Text, create_engine, inspect
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    # 외래 키·인덱스·유니크 제약에 일정한 이름을 붙여 마이그레이션에서 이름으로 다룰 수 있게 한다
    metadata = MetaData(naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    })


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(30), unique=True)   # 로그인 아이디 (소문자로 저장)
    display_name: Mapped[str] = mapped_column(String(50))
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


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
    # 할 일은 작성자와 담당자만 볼 수 있다
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)

    owner: Mapped[User] = relationship(foreign_keys=[owner_id], lazy="joined")
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id], lazy="joined")
    # SQLite(테스트)는 DB 의 ON DELETE CASCADE 를 쓰지 않으므로 ORM 에서도 함께 지운다
    comments: Mapped[list["Comment"]] = relationship(cascade="all, delete-orphan", order_by="Comment.id")
    activities: Mapped[list["Activity"]] = relationship(cascade="all, delete-orphan", order_by="Activity.id")


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    todo_id: Mapped[int] = mapped_column(ForeignKey("todos.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    author: Mapped[User] = relationship(lazy="joined")


class Activity(Base):
    """할 일 생성과 필드 변경 이력. 변경된 필드마다 한 행씩 남긴다."""
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    todo_id: Mapped[int] = mapped_column(ForeignKey("todos.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(20))           # created | updated
    field: Mapped[str | None] = mapped_column(String(30))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    actor: Mapped[User] = relationship(lazy="joined")


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
