import logging
import math
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pwdlib import PasswordHash
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, PlainSerializer, StringConstraints
from sqlalchemy import delete, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import Activity, Comment, Friendship, Notification, Todo, User, get_db, utcnow

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
TOKEN_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "60"))
SECRET_KEY = os.environ.get("JWT_SECRET", "")
if not SECRET_KEY:                               # 로컬 개발용: 서버를 다시 시작하면 기존 토큰은 무효가 된다
    SECRET_KEY = secrets.token_urlsafe(32)
    logger.warning("JWT_SECRET 이 설정되지 않아 임시 키를 사용합니다. 배포 환경에서는 반드시 설정하세요.")
elif len(SECRET_KEY) < 32:
    raise RuntimeError("JWT_SECRET 은 32자 이상이어야 합니다.")

# 같은 계정에서 비밀번호를 연속으로 틀리면 일정 시간 로그인을 막는다 (비밀번호 무작위 대입 방지)
LOGIN_MAX_ATTEMPTS = int(os.environ.get("LOGIN_MAX_ATTEMPTS", "10"))
LOGIN_LOCK_MINUTES = int(os.environ.get("LOGIN_LOCK_MINUTES", "15"))

password_hash = PasswordHash.recommended()       # Argon2
DUMMY_HASH = password_hash.hash(secrets.token_urlsafe(16))   # 없는 아이디도 같은 시간이 걸리도록 비교용
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

router = APIRouter()


Username = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9_]{3,30}$"),
    AfterValidator(str.lower),                   # 대소문자만 다른 아이디는 같은 아이디로 본다
]


def format_utc(value: datetime) -> str:
    # SQLite(테스트)는 시간대를 저장하지 않으므로 시간대 없는 값은 UTC 로 본다
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()


UtcDatetime = Annotated[datetime, PlainSerializer(format_utc, return_type=str, when_used="json")]


class UserCreate(BaseModel):
    username: Username
    display_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
    password: str = Field(min_length=8, max_length=128)


class PasswordConfirm(BaseModel):
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    display_name: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


def create_access_token(user: User) -> str:
    expires = datetime.now(UTC) + timedelta(minutes=TOKEN_MINUTES)
    return jwt.encode({"sub": str(user.id), "exp": expires}, SECRET_KEY, algorithm=ALGORITHM)


def token_user(token: str, db: Session) -> tuple[User, datetime]:
    """토큰을 검증해 사용자와 토큰 만료 시각을 돌려준다."""
    unauthorized = HTTPException(401, "로그인이 필요합니다.", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"require": ["exp", "sub"]})
        user = db.get(User, int(payload["sub"]))
    except (jwt.InvalidTokenError, ValueError):
        raise unauthorized from None
    if user is None:                             # 토큰 발급 후 삭제된 사용자
        raise unauthorized
    return user, datetime.fromtimestamp(payload["exp"], UTC)


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: Session = Depends(get_db)) -> User:
    return token_user(token, db)[0]


CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post("/auth/register", status_code=201)  # 회원가입
def register(payload: UserCreate, db: Session = Depends(get_db)) -> UserOut:
    conflict = HTTPException(409, "이미 사용 중인 아이디입니다.")
    if db.scalar(select(User.id).where(User.username == payload.username)) is not None:
        raise conflict
    user = User(
        username=payload.username,
        display_name=payload.display_name,
        password_hash=password_hash.hash(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:                       # 같은 아이디로 동시에 가입한 경우
        db.rollback()
        raise conflict from None
    db.refresh(user)
    return UserOut.model_validate(user)


def as_utc(value: datetime) -> datetime:
    # SQLite(테스트)는 시간대를 저장하지 않으므로 시간대 없는 값은 UTC 로 본다
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def locked_response(locked_until: datetime) -> HTTPException:
    seconds = max(1, math.ceil((as_utc(locked_until) - utcnow()).total_seconds()))
    return HTTPException(
        429, f"로그인 시도가 너무 많습니다. {math.ceil(seconds / 60)}분 후에 다시 시도하세요.",
        headers={"Retry-After": str(seconds)},
    )


def count_attempt(db: Session, user: User) -> int | None:
    """잠겨 있지 않으면 시도 횟수를 1 올리고 그 값을 돌려준다. 잠겨 있으면 None.
    비밀번호를 확인하기 전에 DB 에서 한 번에 올리므로, 동시에 많이 보내도 허용 횟수를 넘겨 확인하지 않는다."""
    now = utcnow()
    count = db.scalar(
        update(User)
        .where(User.id == user.id, or_(User.locked_until.is_(None), User.locked_until <= now))
        .values(failed_login_count=User.failed_login_count + 1, locked_until=None)
        .returning(User.failed_login_count)
        .execution_options(synchronize_session=False)   # 바로 commit 해서 객체를 다시 읽으므로 맞출 필요 없음
    )
    db.commit()
    return count


def lock(db: Session, user: User) -> HTTPException:
    locked_until = utcnow() + timedelta(minutes=LOGIN_LOCK_MINUTES)
    # 잠금이 풀리면 다시 같은 횟수만큼 시도할 수 있도록 횟수는 0 으로 되돌린다
    db.execute(update(User).where(User.id == user.id).values(failed_login_count=0, locked_until=locked_until))
    db.commit()
    return locked_response(locked_until)


@router.post("/auth/login")                      # 로그인 — Swagger 의 Authorize 버튼과 같은 form 형식
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: Session = Depends(get_db)) -> Token:
    invalid = HTTPException(401, "아이디 또는 비밀번호가 올바르지 않습니다.", headers={"WWW-Authenticate": "Bearer"})
    user = db.scalar(select(User).where(User.username == form.username.strip().lower()))
    if user is None:
        password_hash.verify(form.password, DUMMY_HASH)   # 없는 아이디도 같은 시간이 걸리도록
        raise invalid

    attempt = count_attempt(db, user)
    if attempt is None:                          # 잠긴 동안에는 맞는 비밀번호도 받지 않는다
        db.refresh(user)
        raise locked_response(user.locked_until)
    if attempt > LOGIN_MAX_ATTEMPTS:             # 동시에 들어온 요청이 허용 횟수를 넘긴 경우
        raise lock(db, user)
    if not password_hash.verify(form.password, user.password_hash):
        if attempt == LOGIN_MAX_ATTEMPTS:
            raise lock(db, user)
        raise invalid

    db.execute(update(User).where(User.id == user.id).values(failed_login_count=0))
    db.commit()
    return Token(access_token=create_access_token(user), user=UserOut.model_validate(user))


@router.get("/users/me")                         # 내 정보
def read_me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.delete("/users/me", status_code=204)     # 회원 탈퇴 — 비밀번호를 다시 확인한다
def delete_me(payload: PasswordConfirm, user: CurrentUser, db: Session = Depends(get_db)) -> None:
    if not password_hash.verify(payload.password, user.password_hash):
        # 401 은 "로그인이 풀렸다"는 뜻으로 쓰이므로 403 으로 알린다
        raise HTTPException(403, "비밀번호가 올바르지 않습니다.")
    # SQLite(테스트)는 DB 의 ON DELETE 규칙을 쓰지 않으므로 직접 정리한다
    owned = list(db.scalars(select(Todo).where(Todo.owner_id == user.id)))
    db.execute(update(Notification).where(Notification.todo_id.in_([todo.id for todo in owned])).values(todo_id=None))
    for todo in owned:
        db.delete(todo)                          # 내가 만든 할 일 (댓글·활동 기록 포함)
    db.execute(
        update(Todo).where(Todo.assignee_id == user.id).values(assignee_id=None, assignment_status="accepted")
    )
    db.execute(delete(Notification).where(Notification.user_id == user.id))
    db.execute(update(Comment).where(Comment.author_id == user.id).values(author_id=None))
    db.execute(update(Activity).where(Activity.actor_id == user.id).values(actor_id=None))
    db.execute(delete(Friendship).where(or_(Friendship.requester_id == user.id, Friendship.addressee_id == user.id)))
    db.delete(user)
    db.commit()
