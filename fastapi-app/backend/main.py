from contextlib import asynccontextmanager
import re
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import (
    BaseModel, BeforeValidator, ConfigDict, Field, PlainSerializer, StringConstraints, model_validator,
)
from sqlalchemy import or_, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from prometheus_fastapi_instrumentator import Instrumentator

from .auth import CurrentUser, UserOut, UtcDatetime, router as auth_router
from .database import Activity, Comment, Todo, User, get_db, init_db
from .friends import friend_ids, router as friends_router
from .notifications import detach_todos, notify, router as notifications_router

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

app.include_router(auth_router)                  # 회원가입·로그인·회원 탈퇴
app.include_router(friends_router)               # 친구 요청·친구 목록
app.include_router(notifications_router)         # 사용자별 알림

Status = Literal["planned", "in_progress", "done"]
Tag = Literal["hangout", "work", "important", "trip"]
Priority = Literal["low", "medium", "high"]
AssignmentStatus = Literal["pending", "accepted"]   # 다른 사람에게 할당한 할 일은 담당자가 수락해야 accepted


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
    assignee_id: int | None = None              # 담당자 사용자 id (없으면 미지정)


class TodoIn(TodoFields):                       # 클라이언트가 보내는 데이터 (id 없음)
    @model_validator(mode="after")
    def validate_period(self) -> "TodoIn":
        check_period(self.start_at, self.end_at)
        return self


NULLABLE_FIELDS = {"tag", "assignee_id"}


class TodoPatch(BaseModel):                     # 부분 수정 — 보낸 필드만 바꾼다
    model_config = ConfigDict(extra="forbid")   # 오타난 필드가 조용히 무시되지 않도록

    title: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    start_at: StartAt | None = None
    end_at: EndAt | None = None
    location: str | None = None
    status: Status | None = None
    tag: Tag | None = None                      # 태그와 담당자만 null(없음)로 바꿀 수 있다
    priority: Priority | None = None
    assignee_id: int | None = None

    @model_validator(mode="after")
    def reject_null(self) -> "TodoPatch":
        nulls = sorted(
            name for name in self.model_fields_set if name not in NULLABLE_FIELDS and getattr(self, name) is None
        )
        if nulls:
            raise ValueError(f"null 로 바꿀 수 없는 필드입니다: {', '.join(nulls)}")
        return self


class TodoItem(TodoFields):                      # 서버가 돌려주는 데이터 (id 있음)
    model_config = ConfigDict(from_attributes=True)
    id: int
    owner: UserOut
    assignee: UserOut | None = None
    assignment_status: AssignmentStatus = "accepted"


class RejectIn(BaseModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class CommentIn(BaseModel):
    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class CommentItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    author: UserOut | None                       # None: 탈퇴한 사용자
    body: str
    created_at: UtcDatetime


class ActivityItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    actor: UserOut | None                        # None: 탈퇴한 사용자
    action: Literal["created", "updated"]
    field: str | None
    old_value: str | None
    new_value: str | None
    created_at: UtcDatetime


def can_view(todo: Todo, user: User) -> bool:
    return user.id in (todo.owner_id, todo.assignee_id)


def find_todo(db: Session, todo_id: int, user: User) -> Todo:
    todo = db.get(Todo, todo_id)
    if todo is None or not can_view(todo, user):   # 볼 수 없는 할 일은 존재 여부도 알리지 않는다
        raise HTTPException(404, "To-Do item not found")
    return todo


def check_assignee(db: Session, owner: User, assignee_id: int | None) -> None:
    """담당자는 작성자 본인 또는 작성자의 친구만 될 수 있다."""
    if assignee_id is not None and assignee_id != owner.id and assignee_id not in friend_ids(db, owner.id):
        raise HTTPException(422, "담당자는 본인 또는 친구만 지정할 수 있습니다.")


def activity_value(db: Session, key: str, value: object) -> str | None:
    if value is None:
        return None
    if key == "assignee_id":                     # 친구가 아니게 되거나 탈퇴해도 읽을 수 있도록 이름으로 남긴다
        return db.get(User, value).display_name
    return format_local_datetime(value) if isinstance(value, datetime) else str(value)


def assign(db: Session, todo: Todo, assignee_id: int | None, owner: User) -> None:
    """다른 사람에게 할당하면 수락 대기로 두고 담당자에게 알린다. 본인 할당·미지정은 바로 확정이다."""
    todo.assignee_id = assignee_id
    if assignee_id is None or assignee_id == owner.id:
        todo.assignment_status = "accepted"
        return
    todo.assignment_status = "pending"
    db.flush()                                   # 새 할 일의 id 를 알림에 남기기 위해
    notify(db, assignee_id, "todo_assigned", owner, todo)


def apply_changes(db: Session, todo: Todo, changes: dict, user: User) -> None:
    """바뀐 필드만 반영하고 필드마다 활동 기록을 남긴다."""
    changes = {key: value for key, value in changes.items() if getattr(todo, key) != value}
    if "assignee_id" in changes:
        if user.id != todo.owner_id:             # 담당자가 작성자 모르게 다른 사람에게 넘기지 못하도록
            raise HTTPException(403, "담당자는 작성자만 바꿀 수 있습니다.")
        check_assignee(db, user, changes["assignee_id"])
    for key, value in changes.items():
        old = getattr(todo, key)
        if key == "assignee_id":
            assign(db, todo, value, user)
        else:
            setattr(todo, key, value)
        todo.activities.append(Activity(
            actor_id=user.id, action="updated", field=key,
            old_value=activity_value(db, key, old), new_value=activity_value(db, key, value),
        ))


def saved(db: Session, todo: Todo) -> TodoItem:
    db.commit()
    db.refresh(todo)
    return TodoItem.model_validate(todo)


@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(503, "Database unavailable") from None
    return {"status": "ok"}


@app.get("/todos")                               # 목록 조회 — 내가 작성했거나 담당한 할 일
def get_todos(
    user: CurrentUser,
    scope: Literal["all", "assigned", "owned"] = "all",   # assigned: 내가 담당자인 것만 ("내 할 일")
    db: Session = Depends(get_db),
) -> list[TodoItem]:
    condition = {
        "all": or_(Todo.owner_id == user.id, Todo.assignee_id == user.id),
        "assigned": Todo.assignee_id == user.id,
        "owned": Todo.owner_id == user.id,
    }[scope]
    return [TodoItem.model_validate(todo) for todo in db.scalars(select(Todo).where(condition).order_by(Todo.id))]


@app.post("/todos", status_code=201)             # 추가 — id 는 서버가 매기고 작성자는 로그인한 사용자
def create_todo(payload: TodoIn, user: CurrentUser, db: Session = Depends(get_db)) -> TodoItem:
    check_assignee(db, user, payload.assignee_id)
    todo = Todo(**payload.model_dump(exclude={"assignee_id"}), owner_id=user.id)
    todo.activities.append(Activity(actor_id=user.id, action="created"))
    db.add(todo)
    assign(db, todo, payload.assignee_id, user)
    return saved(db, todo)


@app.put("/todos/{todo_id}")                     # 수정 (상태/태그 포함 전체 갱신)
def update_todo(todo_id: int, payload: TodoIn, user: CurrentUser, db: Session = Depends(get_db)) -> TodoItem:
    todo = find_todo(db, todo_id, user)
    apply_changes(db, todo, payload.model_dump(), user)
    return saved(db, todo)


@app.patch("/todos/{todo_id}")                   # 부분 수정 (예: 상태만 변경)
def patch_todo(todo_id: int, payload: TodoPatch, user: CurrentUser, db: Session = Depends(get_db)) -> TodoItem:
    todo = find_todo(db, todo_id, user)
    changes = payload.model_dump(exclude_unset=True)
    try:
        check_period(changes.get("start_at", todo.start_at), changes.get("end_at", todo.end_at))
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    apply_changes(db, todo, changes, user)
    return saved(db, todo)


@app.delete("/todos/{todo_id}", status_code=204)  # 삭제 — 작성자만 가능
def delete_todo(todo_id: int, user: CurrentUser, db: Session = Depends(get_db)) -> None:
    todo = find_todo(db, todo_id, user)
    if todo.owner_id != user.id:
        raise HTTPException(403, "작성자만 삭제할 수 있습니다.")
    detach_todos(db, [todo.id])
    db.delete(todo)
    db.commit()


def find_pending_assignment(db: Session, todo_id: int, user: User) -> Todo:
    todo = find_todo(db, todo_id, user)
    if todo.assignee_id != user.id or todo.owner_id == user.id:
        raise HTTPException(403, "나에게 할당된 할 일만 수락하거나 거부할 수 있습니다.")
    if todo.assignment_status != "pending":
        raise HTTPException(409, "이미 수락한 할 일입니다.")
    return todo


@app.post("/todos/{todo_id}/accept")             # 할당 수락 — 할당한 사람에게 알린다
def accept_todo(todo_id: int, user: CurrentUser, db: Session = Depends(get_db)) -> TodoItem:
    todo = find_pending_assignment(db, todo_id, user)
    todo.assignment_status = "accepted"
    notify(db, todo.owner_id, "todo_accepted", user, todo)
    return saved(db, todo)


@app.post("/todos/{todo_id}/reject", status_code=204)   # 할당 거부 — 사유와 함께 알리고 할 일은 삭제한다
def reject_todo(todo_id: int, payload: RejectIn, user: CurrentUser, db: Session = Depends(get_db)) -> None:
    todo = find_pending_assignment(db, todo_id, user)
    notify(db, todo.owner_id, "todo_rejected", user, todo, reason=payload.reason)
    detach_todos(db, [todo.id])
    db.delete(todo)
    db.commit()


@app.get("/todos/{todo_id}/comments")            # 댓글 목록 (오래된 순)
def get_comments(todo_id: int, user: CurrentUser, db: Session = Depends(get_db)) -> list[CommentItem]:
    return [CommentItem.model_validate(comment) for comment in find_todo(db, todo_id, user).comments]


@app.post("/todos/{todo_id}/comments", status_code=201)
def create_comment(todo_id: int, payload: CommentIn, user: CurrentUser, db: Session = Depends(get_db)) -> CommentItem:
    todo = find_todo(db, todo_id, user)
    comment = Comment(body=payload.body, author_id=user.id)
    todo.comments.append(comment)
    db.commit()
    db.refresh(comment)
    return CommentItem.model_validate(comment)


@app.delete("/todos/{todo_id}/comments/{comment_id}", status_code=204)  # 본인 댓글만 삭제
def delete_comment(todo_id: int, comment_id: int, user: CurrentUser, db: Session = Depends(get_db)) -> None:
    find_todo(db, todo_id, user)
    comment = db.get(Comment, comment_id)
    if comment is None or comment.todo_id != todo_id:
        raise HTTPException(404, "Comment not found")
    if comment.author_id != user.id:
        raise HTTPException(403, "본인 댓글만 삭제할 수 있습니다.")
    db.delete(comment)
    db.commit()


@app.get("/todos/{todo_id}/activities")          # 활동 기록 (오래된 순)
def get_activities(todo_id: int, user: CurrentUser, db: Session = Depends(get_db)) -> list[ActivityItem]:
    return [ActivityItem.model_validate(activity) for activity in find_todo(db, todo_id, user).activities]


if FRONTEND_DIST.exists():                       # React 빌드 결과물 서빙 (프로덕션)
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
