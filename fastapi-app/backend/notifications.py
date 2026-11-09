import asyncio
import json
import threading
from collections import defaultdict
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, event, select, update
from sqlalchemy.orm import Session

from . import database
from .auth import CurrentUser, UtcDatetime, oauth2_scheme, token_user
from .database import Notification, Todo, User, get_db

router = APIRouter()

MAX_NOTIFICATIONS = 30                           # 사용자마다 최근 알림만 남긴다

# 알림 종류와 문구. 새 종류는 여기와 NotificationType, frontend/src/utils.js 의 NOTIFICATION_TYPES 에 추가한다.
NOTIFICATION_MESSAGES = {
    "todo_assigned": "{actor}님이 일정을 배정했습니다.",
    "todo_rejected": "{actor}님이 일정 배정을 거부했습니다. 거부 사유를 확인해주세요.",
    "todo_accepted": "{actor}님이 일정 배정을 수락했습니다.",
}
NotificationType = Literal["todo_assigned", "todo_rejected", "todo_accepted"]
NotificationStatus = Literal["unread", "read"]

KEEPALIVE_SECONDS = 20                           # 프록시가 유휴 연결을 끊지 않도록 보내는 주석 줄 간격
QUEUE_SIZE = 100                                 # 연결마다 쌓아 둘 이벤트 수. 넘치면 버리고, 클라이언트는 재접속 때 다시 맞춘다


class NotificationHub:
    """사용자별 SSE 연결(asyncio 큐) 목록. 서버 프로세스 하나의 메모리에서만 동작한다.

    동기 라우트는 스레드풀에서 실행되므로 큐에는 각 연결의 이벤트 루프를 통해(call_soon_threadsafe) 넣는다.
    """

    def __init__(self) -> None:
        self._subscribers: dict[int, set[tuple[asyncio.AbstractEventLoop, asyncio.Queue]]] = defaultdict(set)
        self._lock = threading.Lock()

    def subscribe(self, user_id: int) -> tuple[asyncio.AbstractEventLoop, asyncio.Queue]:
        entry = (asyncio.get_running_loop(), asyncio.Queue(maxsize=QUEUE_SIZE))
        with self._lock:
            self._subscribers[user_id].add(entry)
        return entry

    def unsubscribe(self, user_id: int, entry: tuple[asyncio.AbstractEventLoop, asyncio.Queue]) -> None:
        with self._lock:
            connections = self._subscribers.get(user_id)
            if connections is not None:
                connections.discard(entry)
                if not connections:
                    del self._subscribers[user_id]

    def publish(self, user_id: int, message: dict) -> None:
        with self._lock:
            entries = list(self._subscribers.get(user_id, ()))
        for loop, queue in entries:
            try:
                loop.call_soon_threadsafe(_put_nowait, queue, message)
            except RuntimeError:                 # 연결의 이벤트 루프가 이미 닫힘
                pass


def _put_nowait(queue: asyncio.Queue, message: dict) -> None:
    try:
        queue.put_nowait(message)
    except asyncio.QueueFull:
        pass


hub = NotificationHub()

PENDING_KEY = "pending_notifications"           # 커밋 전까지 보낼 알림을 Session.info 에 모아 둔다


@event.listens_for(Session, "after_commit")
def _publish_committed(session: Session) -> None:
    """DB 에 저장이 끝난 알림만 실시간으로 보낸다."""
    for user_id, type_ in session.info.pop(PENDING_KEY, []):
        hub.publish(user_id, {"type": type_})


@event.listens_for(Session, "after_rollback")
def _discard_rolled_back(session: Session) -> None:
    session.info.pop(PENDING_KEY, None)


class NotificationItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    type: NotificationType
    message: str
    status: NotificationStatus
    created_at: UtcDatetime
    todo_id: int | None                          # None: 할 일이 삭제됨 (예: 할당 거부)
    todo_title: str | None
    reason: str | None                           # 할일 할당 거부 사유


def notify(
    db: Session, recipient_id: int, type_: NotificationType, actor: User, todo: Todo, reason: str | None = None,
) -> None:
    """알림을 추가하고 받는 사람의 알림이 MAX_NOTIFICATIONS 개를 넘으면 오래된 것부터 지운다. 커밋은 호출한 쪽이 한다."""
    db.add(Notification(
        user_id=recipient_id, type=type_, message=NOTIFICATION_MESSAGES[type_].format(actor=actor.display_name),
        todo_id=todo.id, todo_title=todo.title, reason=reason,
    ))
    db.info.setdefault(PENDING_KEY, []).append((recipient_id, type_))
    db.flush()
    stale = select(Notification.id).where(Notification.user_id == recipient_id) \
        .order_by(Notification.id.desc()).offset(MAX_NOTIFICATIONS)
    db.execute(delete(Notification).where(Notification.id.in_(stale.scalar_subquery())))


def detach_todos(db: Session, todo_ids: list[int]) -> None:
    """삭제되는 할 일을 가리키는 알림의 연결만 끊는다. (SQLite 는 ON DELETE SET NULL 을 쓰지 않으므로 직접 처리)"""
    if todo_ids:
        db.execute(update(Notification).where(Notification.todo_id.in_(todo_ids)).values(todo_id=None))


@router.get("/notifications")                    # 내 알림 목록 (최신순)
def list_notifications(user: CurrentUser, db: Session = Depends(get_db)) -> list[NotificationItem]:
    notifications = db.scalars(
        select(Notification).where(Notification.user_id == user.id).order_by(Notification.id.desc())
    )
    return [NotificationItem.model_validate(notification) for notification in notifications]


def sse(event_name: str, data: dict) -> str:
    return f"event: {event_name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def event_stream(user_id: int, expires_at: datetime) -> AsyncIterator[str]:
    """새 알림이 생길 때마다 이벤트를 보낸다. 로그인 토큰이 만료되면 스트림을 끝낸다(재접속 시 401 → 로그아웃)."""
    entry = hub.subscribe(user_id)
    try:
        # 연결(재연결) 직후 클라이언트가 그 사이 놓친 알림을 다시 불러오도록 알린다
        yield "retry: 3000\n" + sse("ready", {})
        while (remaining := (expires_at - datetime.now(UTC)).total_seconds()) > 0:
            try:
                message = await asyncio.wait_for(entry[1].get(), timeout=min(KEEPALIVE_SECONDS, remaining))
            except TimeoutError:
                yield ": keep-alive\n\n"
                continue
            yield sse("notification", message)
    finally:                                     # 클라이언트가 끊으면 Starlette 가 생성기를 취소한다
        hub.unsubscribe(user_id, entry)


def stream_owner(token: str) -> tuple[int, datetime]:
    # 스트림이 열려 있는 동안 DB 연결을 붙잡지 않도록 인증할 때만 세션을 연다
    with database.SessionLocal() as db:
        user, expires_at = token_user(token, db)
        return user.id, expires_at


@router.get("/notifications/stream")             # 실시간 알림 (Server-Sent Events)
async def stream_notifications(token: Annotated[str, Depends(oauth2_scheme)]) -> StreamingResponse:
    user_id, expires_at = await run_in_threadpool(stream_owner, token)
    return StreamingResponse(
        event_stream(user_id, expires_at),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},   # 프록시 버퍼링 방지
    )


@router.post("/notifications/read-all", status_code=204)   # 모두 확인 처리
def read_all(user: CurrentUser, db: Session = Depends(get_db)) -> None:
    db.execute(update(Notification).where(Notification.user_id == user.id).values(status="read"))
    db.commit()


@router.post("/notifications/{notification_id}/read")      # 알림 하나 확인 처리
def read_notification(notification_id: int, user: CurrentUser, db: Session = Depends(get_db)) -> NotificationItem:
    notification = db.get(Notification, notification_id)
    if notification is None or notification.user_id != user.id:
        raise HTTPException(404, "알림을 찾을 수 없습니다.")
    notification.status = "read"
    db.commit()
    db.refresh(notification)
    return NotificationItem.model_validate(notification)
