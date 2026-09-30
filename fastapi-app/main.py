import json
import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent       # main.py 가 있는 폴더
LEGACY_TODO_FILE = BASE_DIR / "todo.json"
TODO_FILE = Path(os.environ.get("TODO_FILE", str(LEGACY_TODO_FILE)))
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"    # React 빌드 산출물

if not TODO_FILE.exists():
    TODO_FILE.parent.mkdir(parents=True, exist_ok=True)
    if TODO_FILE != LEGACY_TODO_FILE and LEGACY_TODO_FILE.exists():
        TODO_FILE.write_text(LEGACY_TODO_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        TODO_FILE.write_text("[]", encoding="utf-8")

app = FastAPI(title="To-Do List API")

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


class TodoIn(BaseModel):                         # 클라이언트가 보내는 데이터 (id 없음)
    title: str = Field(min_length=1, max_length=100)
    description: str = ""
    start_at: str | None = None                  # 기간 시작 일시 (YYYY-MM-DDTHH:MM)
    end_at: str | None = None                    # 마감 일시 (YYYY-MM-DDTHH:MM)
    location: str = ""
    status: Status = "planned"
    tag: Tag | None = None
    priority: Priority = "medium"
    assignee: str = ""


class TodoItem(TodoIn):                          # 서버가 돌려주는 데이터 (id 있음)
    id: int


def _migrate(raw: dict) -> dict:
    """구버전 데이터(completed/steps)를 칸반 스키마로 보정한다."""
    data = dict(raw)
    legacy_due_date = data.pop("due_date", "") or ""
    if legacy_due_date:
        previous_end = data.get("end_at")
        end_time = previous_end.split("T", 1)[1][:5] if isinstance(previous_end, str) and "T" in previous_end else ""
        if len(end_time) != 5 or end_time[2] != ":":
            end_time = "23:59"
        data["end_at"] = f"{legacy_due_date}T{end_time}"
    if "status" not in data:
        data["status"] = "done" if data.pop("completed", False) else "planned"
    else:
        data.pop("completed", None)
    data.pop("steps", None)
    data.setdefault("tag", None)
    data.setdefault("priority", "medium")
    data.setdefault("assignee", "")
    return data


def load_todos() -> list[TodoItem]:
    raw = TODO_FILE.read_text(encoding="utf-8") if TODO_FILE.exists() else "[]"
    return [TodoItem(**_migrate(t)) for t in json.loads(raw)]


def save_todos(todos: list[TodoItem]) -> None:
    data = json.dumps([t.model_dump() for t in todos], indent=2, ensure_ascii=False)
    TODO_FILE.write_text(data, encoding="utf-8")


def find_index(todos: list[TodoItem], todo_id: int) -> int:
    for i, todo in enumerate(todos):
        if todo.id == todo_id:
            return i
    raise HTTPException(404, "To-Do item not found")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/todos")                               # 목록 조회
def get_todos() -> list[TodoItem]:
    return load_todos()


@app.post("/todos", status_code=201)             # 추가 — id 는 서버가 매긴다
def create_todo(payload: TodoIn) -> TodoItem:
    todos = load_todos()
    new_id = max((t.id for t in todos), default=0) + 1
    todo = TodoItem(id=new_id, **payload.model_dump())
    save_todos(todos + [todo])
    return todo


@app.put("/todos/{todo_id}")                     # 수정 (상태/태그 포함 전체 갱신)
def update_todo(todo_id: int, payload: TodoIn) -> TodoItem:
    todos = load_todos()
    idx = find_index(todos, todo_id)
    todo = TodoItem(id=todo_id, **payload.model_dump())
    todos[idx] = todo
    save_todos(todos)
    return todo


@app.delete("/todos/{todo_id}", status_code=204)  # 삭제
def delete_todo(todo_id: int) -> None:
    todos = load_todos()
    del todos[find_index(todos, todo_id)]
    save_todos(todos)


if FRONTEND_DIST.exists():                       # React 빌드 결과물 서빙 (프로덕션)
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")