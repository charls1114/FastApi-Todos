from contextlib import asynccontextmanager
import re
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PlainSerializer, model_validator
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from prometheus_fastapi_instrumentator import Instrumentator

from .database import Todo, get_db, init_db

BASE_DIR = Path(__file__).resolve().parent.parent  # fastapi-app 폴더
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"    # React 빌드 산출물


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="To-Do List API", lifespan=lifespan)

Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)  # Prometheus 메트릭 수집 및 엔드포인트 노출

# Vite 개발 서버(기본 5173 포트)에서 API를 호출할 수 있도록 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

Status = Literal["planned", "in_progress", "done"]
Tag = Literal["hangout", "work", "important", "trip"]
Priority = Literal["low", "medium", "high"]


DATETIME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?)?$")   # YYYY-MM-DD[THH:MM[:SS]]
INVALID_DATETIME = "유효한 날짜와 시각을 입력해야 합니다."


def parse_local_datetime(value: object, end_of_day: bool) -> datetime:
    """시간대 없는 로컬 일시 문자열을 datetime 으로 바꾼다. 날짜만 있으면 그날의 시작 또는 끝으로 본다."""
    if isinstance(value, datetime):              # DB 에서 읽은 값
        return value
    if not isinstance(value, str) or not DATETIME_PATTERN.match(value):
        raise ValueError(INVALID_DATETIME)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError(INVALID_DATETIME) from None
    if "T" not in value and end_of_day:
        parsed = parsed.replace(hour=23, minute=59, second=59)
    return parsed


def format_local_datetime(value: datetime) -> str:
    return value.isoformat(timespec="seconds" if value.second else "minutes")   # 2026-10-13T09:00


# 응답(JSON)에서는 기존과 같은 YYYY-MM-DDTHH:MM[:SS] 문자열로 내보낸다
DatetimeOut = PlainSerializer(format_local_datetime, return_type=str, when_used="json")
StartAt = Annotated[datetime, BeforeValidator(partial(parse_local_datetime, end_of_day=False)), DatetimeOut]
EndAt = Annotated[datetime, BeforeValidator(partial(parse_local_datetime, end_of_day=True)), DatetimeOut]


def check_period(start_at: datetime, end_at: datetime) -> None:
    if end_at < start_at:
        raise ValueError("종료 일시는 시작 일시 이후여야 합니다.")


class TodoFields(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: str = ""
    start_at: StartAt
    end_at: EndAt
    location: str = ""
    status: Status = "planned"
    tag: Tag | None = None
    priority: Priority = "medium"
    assignee: str = ""


class TodoIn(TodoFields):                       # 클라이언트가 보내는 데이터 (id 없음)
    @model_validator(mode="after")
    def validate_period(self) -> "TodoIn":
        check_period(self.start_at, self.end_at)
        return self


class TodoPatch(BaseModel):                     # 부분 수정 — 보낸 필드만 바꾼다
    model_config = ConfigDict(extra="forbid")   # 오타난 필드가 조용히 무시되지 않도록

    title: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    start_at: StartAt | None = None
    end_at: EndAt | None = None
    location: str | None = None
    status: Status | None = None
    tag: Tag | None = None                      # 태그만 null(태그 없음)로 바꿀 수 있다
    priority: Priority | None = None
    assignee: str | None = None

    @model_validator(mode="after")
    def reject_null(self) -> "TodoPatch":
        nulls = sorted(name for name in self.model_fields_set if name != "tag" and getattr(self, name) is None)
        if nulls:
            raise ValueError(f"null 로 바꿀 수 없는 필드입니다: {', '.join(nulls)}")
        return self


class TodoItem(TodoFields):                      # 서버가 돌려주는 데이터 (id 있음)
    model_config = ConfigDict(from_attributes=True)
    id: int


def find_todo(db: Session, todo_id: int) -> Todo:
    todo = db.get(Todo, todo_id)
    if todo is None:
        raise HTTPException(404, "To-Do item not found")
    return todo

@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(503, "Database unavailable") from None
    return {"status": "ok"}

@app.get("/todos")                               # 목록 조회
def get_todos(db: Session = Depends(get_db)) -> list[TodoItem]:
    return [TodoItem.model_validate(todo) for todo in db.scalars(select(Todo).order_by(Todo.id))]


@app.post("/todos", status_code=201)             # 추가 — id 는 서버가 매긴다
def create_todo(payload: TodoIn, db: Session = Depends(get_db)) -> TodoItem:
    todo = Todo(**payload.model_dump())
    db.add(todo)
    db.commit()
    db.refresh(todo)
    return TodoItem.model_validate(todo)


@app.put("/todos/{todo_id}")                     # 수정 (상태/태그 포함 전체 갱신)
def update_todo(todo_id: int, payload: TodoIn, db: Session = Depends(get_db)) -> TodoItem:
    todo = find_todo(db, todo_id)
    for key, value in payload.model_dump().items():
        setattr(todo, key, value)
    db.commit()
    db.refresh(todo)
    return TodoItem.model_validate(todo)


@app.patch("/todos/{todo_id}")                   # 부분 수정 (예: 상태만 변경)
def patch_todo(todo_id: int, payload: TodoPatch, db: Session = Depends(get_db)) -> TodoItem:
    todo = find_todo(db, todo_id)
    changes = payload.model_dump(exclude_unset=True)
    try:
        check_period(changes.get("start_at", todo.start_at), changes.get("end_at", todo.end_at))
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    for key, value in changes.items():
        setattr(todo, key, value)
    db.commit()
    db.refresh(todo)
    return TodoItem.model_validate(todo)


@app.delete("/todos/{todo_id}", status_code=204)  # 삭제
def delete_todo(todo_id: int, db: Session = Depends(get_db)) -> None:
    db.delete(find_todo(db, todo_id))
    db.commit()


if FRONTEND_DIST.exists():                       # React 빌드 결과물 서빙 (프로덕션)
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
