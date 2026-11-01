from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import CurrentUser, UserOut, Username
from .database import Friendship, User, get_db

router = APIRouter()


class FriendRequestIn(BaseModel):
    username: Username


class FriendRequestItem(BaseModel):
    id: int
    user: UserOut                                # 요청을 주고받은 상대방
    status: Literal["pending", "accepted"]
    created_at: datetime


class FriendRequests(BaseModel):
    received: list[FriendRequestItem]
    sent: list[FriendRequestItem]


def between(a: int, b: int):
    """두 사용자 사이의 요청·관계 (방향 무관)."""
    return or_(
        and_(Friendship.requester_id == a, Friendship.addressee_id == b),
        and_(Friendship.requester_id == b, Friendship.addressee_id == a),
    )


def friend_ids(db: Session, user_id: int) -> set[int]:
    rows = db.execute(
        select(Friendship.requester_id, Friendship.addressee_id).where(
            Friendship.status == "accepted",
            or_(Friendship.requester_id == user_id, Friendship.addressee_id == user_id),
        )
    )
    return {b if a == user_id else a for a, b in rows}


def request_item(friendship: Friendship, me: User) -> FriendRequestItem:
    other = friendship.addressee if friendship.requester_id == me.id else friendship.requester
    return FriendRequestItem(
        id=friendship.id, user=UserOut.model_validate(other),
        status=friendship.status, created_at=friendship.created_at,
    )


def find_request(db: Session, request_id: int, user: User) -> Friendship:
    friendship = db.get(Friendship, request_id)
    if friendship is None or friendship.status != "pending" or user.id not in (
        friendship.requester_id, friendship.addressee_id,
    ):
        raise HTTPException(404, "친구 요청을 찾을 수 없습니다.")
    return friendship


@router.get("/friends")                          # 친구 목록 (담당자 선택에도 쓴다)
def list_friends(user: CurrentUser, db: Session = Depends(get_db)) -> list[UserOut]:
    ids = friend_ids(db, user.id)
    users = db.scalars(select(User).where(User.id.in_(ids)).order_by(User.display_name, User.id)) if ids else []
    return [UserOut.model_validate(friend) for friend in users]


@router.delete("/friends/{user_id}", status_code=204)   # 친구 끊기 — 이미 맡긴 할 일의 담당자는 그대로 둔다
def remove_friend(user_id: int, user: CurrentUser, db: Session = Depends(get_db)) -> None:
    result = db.execute(delete(Friendship).where(between(user.id, user_id), Friendship.status == "accepted"))
    if result.rowcount == 0:
        raise HTTPException(404, "친구가 아닙니다.")
    db.commit()


@router.get("/friends/requests")                 # 받은 요청과 보낸 요청 (대기 중인 것만)
def list_requests(user: CurrentUser, db: Session = Depends(get_db)) -> FriendRequests:
    pending = db.scalars(
        select(Friendship)
        .where(Friendship.status == "pending", or_(Friendship.requester_id == user.id, Friendship.addressee_id == user.id))
        .order_by(Friendship.id)
    )
    requests = FriendRequests(received=[], sent=[])
    for friendship in pending:
        bucket = requests.sent if friendship.requester_id == user.id else requests.received
        bucket.append(request_item(friendship, user))
    return requests


@router.post("/friends/requests", status_code=201)   # 아이디로 친구 요청 — 상대도 나에게 요청했다면 바로 친구가 된다
def send_request(payload: FriendRequestIn, user: CurrentUser, db: Session = Depends(get_db)) -> FriendRequestItem:
    target = db.scalar(select(User).where(User.username == payload.username))
    if target is None:
        raise HTTPException(404, "존재하지 않는 아이디입니다.")
    if target.id == user.id:
        raise HTTPException(422, "자기 자신에게는 친구 요청을 보낼 수 없습니다.")

    existing = db.scalar(select(Friendship).where(between(user.id, target.id)))
    if existing is not None and existing.status == "accepted":
        raise HTTPException(409, "이미 친구입니다.")
    if existing is not None and existing.requester_id == user.id:
        raise HTTPException(409, "이미 친구 요청을 보냈습니다.")
    if existing is not None:                     # 상대가 먼저 보낸 요청을 수락한 것으로 본다
        existing.status = "accepted"
        friendship = existing
    else:
        friendship = Friendship(requester_id=user.id, addressee_id=target.id)
        db.add(friendship)
    try:
        db.commit()
    except IntegrityError:                       # 같은 요청을 동시에 보낸 경우
        db.rollback()
        raise HTTPException(409, "이미 친구 요청을 보냈습니다.") from None
    db.refresh(friendship)
    return request_item(friendship, user)


@router.post("/friends/requests/{request_id}/accept")   # 받은 요청 수락
def accept_request(request_id: int, user: CurrentUser, db: Session = Depends(get_db)) -> FriendRequestItem:
    friendship = find_request(db, request_id, user)
    if friendship.addressee_id != user.id:
        raise HTTPException(403, "받은 요청만 수락할 수 있습니다.")
    friendship.status = "accepted"
    db.commit()
    db.refresh(friendship)
    return request_item(friendship, user)


@router.delete("/friends/requests/{request_id}", status_code=204)   # 받은 요청 거절 또는 보낸 요청 취소
def delete_request(request_id: int, user: CurrentUser, db: Session = Depends(get_db)) -> None:
    db.delete(find_request(db, request_id, user))
    db.commit()
