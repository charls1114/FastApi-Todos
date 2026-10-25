from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .database import Todo, get_db, init_db

BASE_DIR = Path(__file__).resolve().parent.parent  # fastapi-app 폴더
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"    # React 빌드 산출물


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="To-Do List API", lifespan=lifespan)

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


DATETIME_PATTERN = r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?)?$"   # YYYY-MM-DD[THH:MM[:SS]]


class TodoIn(BaseModel):                        # 클라이언트가 보내는 데이터 (id 없음)
    title: str = Field(min_length=1, max_length=100)
    description: str = ""
    start_at: str = Field(pattern=DATETIME_PATTERN)
    end_at: str = Field(pattern=DATETIME_PATTERN)
    location: str = ""
    status: Status = "planned"
    tag: Tag | None = None
    priority: Priority = "medium"
    assignee: str = ""

    @model_validator(mode="after")
    def check_period(self) -> "TodoIn":
        # 날짜만 있으면 시작은 그날 0시, 종료는 그날의 끝으로 보고 비교
        start = self.start_at if "T" in self.start_at else f"{self.start_at}T00:00"
        end = self.end_at if "T" in self.end_at else f"{self.end_at}T23:59:59"
        if end < start:
            raise ValueError("종료 일시는 시작 일시 이후여야 합니다.")
        return self


class TodoItem(TodoIn):                          # 서버가 돌려주는 데이터 (id 있음)
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


@app.delete("/todos/{todo_id}", status_code=204)  # 삭제
def delete_todo(todo_id: int, db: Session = Depends(get_db)) -> None:
    db.delete(find_todo(db, todo_id))
    db.commit()


if FRONTEND_DIST.exists():                       # React 빌드 결과물 서빙 (프로덕션)
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
