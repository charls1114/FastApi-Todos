from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from backend.database import Base, database_url

config = context.config
if config.config_file_name is not None:          # alembic CLI 로 실행할 때만 로그 설정 적용
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations(connection) -> None:
    # render_as_batch: SQLite(테스트)에서도 컬럼 변경이 되도록 테이블을 새로 만들어 옮긴다
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(url=database_url().render_as_string(hide_password=False), target_metadata=target_metadata,
                      literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
elif (connection := config.attributes.get("connection")) is not None:   # init_db() 가 넘긴 연결
    run_migrations(connection)
else:
    with create_engine(database_url()).connect() as connection:
        run_migrations(connection)
