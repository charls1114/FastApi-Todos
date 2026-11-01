import logging
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pwdlib import PasswordHash
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import delete, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import Activity, Comment, Friendship, Todo, User, get_db

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
TOKEN_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "60"))
SECRET_KEY = os.environ.get("JWT_SECRET", "")
if not SECRET_KEY:                               # 로컬 개발용: 서버를 다시 시작하면 기존 토큰은 무효가 된다
    SECRET_KEY = secrets.token_urlsafe(32)
    logger.warning("JWT_SECRET 이 설정되지 않아 임시 키를 사용합니다. 배포 환경에서는 반드시 설정하세요.")
elif len(SECRET_KEY) < 32:
    raise RuntimeError("JWT_SECRET 은 32자 이상이어야 합니다.")

password_hash = PasswordHash.recommended()       # Argon2
DUMMY_HASH = password_hash.hash(secrets.token_urlsafe(16))   # 없는 아이디도 같은 시간이 걸리도록 비교용
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

router = APIRouter()


Username = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9_]{3,30}$"),
    AfterValidator(str.lower),                   # 대소문자만 다른 아이디는 같은 아이디로 본다
]


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


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: Session = Depends(get_db)) -> User:
    unauthorized = HTTPException(401, "로그인이 필요합니다.", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"require": ["exp", "sub"]})
        user = db.get(User, int(payload["sub"]))
    except (jwt.InvalidTokenError, ValueError):
        raise unauthorized from None
    if user is None:                             # 토큰 발급 후 삭제된 사용자
        raise unauthorized
    return user


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


@router.post("/auth/login")                      # 로그인 — Swagger 의 Authorize 버튼과 같은 form 형식
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: Session = Depends(get_db)) -> Token:
    user = db.scalar(select(User).where(User.username == form.username.strip().lower()))
    if not password_hash.verify(form.password, user.password_hash if user else DUMMY_HASH) or user is None:
        raise HTTPException(401, "아이디 또는 비밀번호가 올바르지 않습니다.", headers={"WWW-Authenticate": "Bearer"})
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
    for todo in db.scalars(select(Todo).where(Todo.owner_id == user.id)):
        db.delete(todo)                          # 내가 만든 할 일 (댓글·활동 기록 포함)
    db.execute(update(Todo).where(Todo.assignee_id == user.id).values(assignee_id=None))
    db.execute(update(Comment).where(Comment.author_id == user.id).values(author_id=None))
    db.execute(update(Activity).where(Activity.actor_id == user.id).values(actor_id=None))
    db.execute(delete(Friendship).where(or_(Friendship.requester_id == user.id, Friendship.addressee_id == user.id)))
    db.delete(user)
    db.commit()
