# FastApi-Todos

FastAPI와 React로 만든 칸반 방식의 할 일 관리 웹 애플리케이션입니다. 할 일을 예정, 진행 중, 완료 상태로 나누어 관리하고, 카드 드래그 앤 드롭으로 작업 상태를 변경할 수 있습니다.

## 주요 기능

- 회원가입·로그인(JWT)과 사용자별 할 일: 할 일은 작성자와 담당자만 보고 수정할 수 있으며, 삭제는 작성자만 가능
- 아이디로 친구 요청을 보내고, 상대가 수락하면 친구가 됨 (받은 요청 수락·거절, 보낸 요청 취소, 친구 끊기)
- 담당자는 본인 또는 친구 중에서만 지정하고 "내 할 일"(내가 담당) / "내가 만든 일"로 걸러 보기
- 비밀번호를 다시 확인하는 회원 탈퇴
- 카드별 댓글과 활동 기록(생성, 필드별 변경 이력)
- 칸반 보드에서 할 일 추가, 수정, 삭제 및 상태 변경
- 내비게이션 버튼으로 칸반 보드와 월간 달력 보기 전환
- 시작일·종료일·마감일에 따른 달력 표시 및 날짜별 할 일 추가
- 제목과 설명으로 카드 검색
- 설명, 시작·마감 일시, 장소, 태그, 우선순위 관리
- 전체 할 일 중 완료된 항목 수와 진행률 표시
- 마감일이 지난 항목 표시
- PostgreSQL 기반 데이터 저장 및 Docker named volume을 통한 데이터 유지
- FastAPI의 OpenAPI 문서 제공

## 기술 스택

- 프런트엔드: React 19, Vite 8, Tailwind CSS 4
- 백엔드: Python 3.13, FastAPI, Uvicorn
- 저장소: PostgreSQL 17, SQLAlchemy, Psycopg 3
- 배포: Docker, Docker Compose, 멀티 스테이지 이미지 빌드

## 빠른 시작: Docker Compose

Docker와 Docker Compose가 설치된 환경에서 저장소 루트에서 실행합니다.

```bash
cp .env.example .env
# .env의 POSTGRES_PASSWORD와 JWT_SECRET(32자 이상 임의 값)을 변경한 뒤 실행합니다.
docker compose up --build -d
```

브라우저에서 [http://localhost:5001](http://localhost:5001)을 열면 애플리케이션을 사용할 수 있습니다. API 문서는 [http://localhost:5001/docs](http://localhost:5001/docs), 상태 확인은 [http://localhost:5001/health](http://localhost:5001/health)에서 확인할 수 있습니다.

PowerShell에서는 `Copy-Item .env.example .env`로 설정 파일을 복사합니다. API는 PostgreSQL의 준비 상태를 확인한 후 시작하며, 시작할 때마다 Alembic 마이그레이션을 최신 버전까지 자동으로 적용합니다(`alembic upgrade head`와 같음). Alembic 도입 전에 만들어진 DB는 기준 버전(`0001`)으로 표시한 뒤 이어서 업그레이드합니다.

데이터는 `postgres-data` named volume에 저장되므로 컨테이너를 다시 만들어도 유지됩니다. `docker compose down`은 볼륨을 보존합니다. `docker compose down -v`는 DB를 포함한 볼륨 데이터를 삭제하므로 주의하세요. PostgreSQL 포트는 로컬 호스트에만 공개합니다.

```bash
docker compose down
```

새 PostgreSQL 볼륨은 빈 할 일 목록으로 시작합니다. 이후 추가한 데이터는 재시작해도 유지됩니다.

## 로컬 개발

백엔드와 프런트엔드는 각각 별도 터미널에서 실행합니다. Python 3.13 이상과 Node.js 22 이상이 필요합니다.

### 백엔드

먼저 저장소 루트에서 `.env`를 준비하고 `docker compose up -d postgres`로 DB를 실행합니다. 아래 PowerShell 예시의 비밀번호와 포트는 `.env` 설정에 맞춥니다.

```powershell
cd fastapi-app
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:POSTGRES_PASSWORD = "change-this-local-password"
# .env에서 POSTGRES_DB, POSTGRES_USER, POSTGRES_PORT도 바꿨다면 같은 환경변수를 설정합니다.
uvicorn backend.main:app --reload --port 8000
```

개발 API는 `http://localhost:8000`에서 실행됩니다.

#### DB 마이그레이션

스키마는 Alembic으로 관리하며 마이그레이션 파일은 `fastapi-app/backend/migrations/versions/`에 있습니다. 앱이 시작될 때 자동으로 적용되므로 직접 실행할 필요는 없습니다. 스키마를 바꿀 때는 `backend/database.py`의 모델을 수정한 뒤 `fastapi-app` 폴더에서 다음을 실행합니다. DB 연결 정보는 앱과 같은 환경변수를 사용합니다.

```bash
alembic revision --autogenerate -m "변경 내용"   # 생성된 파일을 검토한 뒤 커밋
alembic upgrade head                            # 앱을 시작하지 않고 적용할 때
alembic check                                   # 모델과 마이그레이션이 일치하는지 확인
```

`0002` 마이그레이션은 `start_at`, `end_at`을 문자열에서 `TIMESTAMP`로 바꿉니다. 날짜만 저장된 값은 시작은 그날 0시, 종료는 그날 23:59:59로 변환합니다. 날짜로 읽을 수 없는 값(예: `2026-02-30`)이 있으면 아무것도 바꾸지 않고 해당 ID를 알려주며 실패하므로, 그 행을 고친 뒤 다시 시작합니다.

`0004` 마이그레이션은 친구 요청·관계를 저장하는 `friendships` 테이블을 추가합니다.

`0003` 마이그레이션은 `users`, `comments`, `activities` 테이블을 만들고, `todos`의 자유 텍스트 `assignee`를 사용자 ID인 `assignee_id`로 바꾸며 작성자 `owner_id`를 추가합니다. **기존 할 일은 작성자를 알 수 없으므로 모두 삭제됩니다.** 필요하면 업그레이드 전에 `pg_dump`로 백업하세요.

외부 PostgreSQL은 `DATABASE_URL=postgresql+psycopg://user:password@host:5432/dbname`으로 연결할 수 있습니다. 이 값은 `POSTGRES_*` 환경변수보다 우선합니다. URL의 비밀번호에 특수문자가 있으면 URL 인코딩이 필요합니다. `POSTGRES_*` 방식은 인코딩 없이 비밀번호를 사용합니다. 로컬 Uvicorn 실행은 루트 `.env`를 자동으로 읽지 않으므로 환경변수를 직접 설정합니다.

### 프런트엔드

다른 터미널에서 저장소 루트 기준으로:

```bash
cd fastapi-app/frontend
npm ci
npm run dev
```

Vite가 출력하는 주소(기본값 `http://localhost:5173`)를 엽니다. 개발 서버의 `/todos` 요청은 `http://localhost:8000`으로 프록시됩니다. 프로덕션에서는 Docker 이미지 빌드 중 React 앱을 빌드하고 FastAPI가 정적 파일을 함께 제공합니다.

### 테스트

저장소 루트에서 다음을 실행합니다.

```bash
cd fastapi-app
pytest tests/test_main.py tests/test_database.py tests/test_migrations.py tests/test_auth.py tests/test_collaboration.py tests/test_friends.py
```

기본 API 테스트는 임시 SQLite DB를 사용합니다. 실제 PostgreSQL 검증은 `TEST_DATABASE_URL`을 별도의 테스트 DB 연결 문자열로 설정한 뒤 같은 명령을 실행합니다. 각 테스트는 임의의 전용 스키마를 생성하고 종료 시 제거하므로 테스트 계정에 스키마 생성 권한이 필요합니다. 배포 및 UI 테스트는 기존처럼 `BASE_URL`을 지정한 실행 서버를 대상으로 별도 실행합니다. 배포·UI·k6 테스트는 실행할 때마다 임시 계정을 만들고 끝나면 탈퇴하므로 테스트 계정이 DB에 남지 않습니다.

## API

모든 할 일 데이터는 `/todos` 경로에서 JSON으로 주고받습니다.

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| `POST` | `/auth/register` | 회원가입 (성공 시 `201`, 아이디 중복 시 `409`) |
| `POST` | `/auth/login` | 로그인. form(`username`, `password`)으로 보내고 `access_token`을 받음 |
| `GET` | `/users/me` | 내 정보 |
| `DELETE` | `/users/me` | 회원 탈퇴. 본문 `{"password": "..."}`로 비밀번호를 다시 확인 (틀리면 `403`) |
| `GET` | `/friends` | 친구 목록 (담당자 선택용) |
| `DELETE` | `/friends/{user_id}` | 친구 끊기 |
| `GET` | `/friends/requests` | 대기 중인 친구 요청 (`received`: 받은 요청, `sent`: 보낸 요청) |
| `POST` | `/friends/requests` | 아이디(`username`)로 친구 요청. 상대가 이미 나에게 요청했다면 바로 친구가 됨 |
| `POST` | `/friends/requests/{request_id}/accept` | 받은 친구 요청 수락 |
| `DELETE` | `/friends/requests/{request_id}` | 받은 요청 거절 또는 보낸 요청 취소 |
| `GET` | `/todos?scope=all\|assigned\|owned` | 할 일 목록. `assigned`는 내가 담당자인 것("내 할 일"), `owned`는 내가 만든 것 |
| `POST` | `/todos` | 할 일 생성 (성공 시 `201`) |
| `PUT` | `/todos/{todo_id}` | 할 일 전체 수정 |
| `PATCH` | `/todos/{todo_id}` | 할 일 부분 수정 (보낸 필드만 변경) |
| `DELETE` | `/todos/{todo_id}` | 할 일 삭제 (작성자만, 성공 시 `204`) |
| `GET` / `POST` | `/todos/{todo_id}/comments` | 댓글 목록 / 작성 |
| `DELETE` | `/todos/{todo_id}/comments/{comment_id}` | 댓글 삭제 (본인 댓글만) |
| `GET` | `/todos/{todo_id}/activities` | 활동 기록 |
| `GET` | `/health` | 서비스 상태 확인 (로그인 불필요) |

`/health`와 회원가입·로그인을 제외한 모든 API는 `Authorization: Bearer <access_token>` 헤더가 필요하며, 없거나 만료된 토큰에는 `401`을 반환합니다. 토큰 유효 시간은 `JWT_EXPIRE_MINUTES`(기본 60분)입니다. Swagger UI(`/docs`)에서는 오른쪽 위 **Authorize** 버튼으로 로그인할 수 있습니다.

할 일은 작성자와 담당자에게만 보입니다. 다른 사용자의 할 일에 접근하면 존재 여부를 알리지 않도록 `404`를 반환하고, 담당자가 삭제하려 하거나 남의 댓글을 지우려 하면 `403`을 반환합니다. 활동 기록은 생성 시 한 줄, 수정 시 실제로 바뀐 필드마다 한 줄(`field`, `old_value`, `new_value`)씩 남습니다. 댓글·활동 기록의 `created_at`은 UTC 시각(`+00:00`)입니다.

담당자(`assignee_id`)는 작성자 본인 또는 작성자의 친구만 지정할 수 있고(아니면 `422`), 담당자를 바꾸는 것은 작성자만 할 수 있습니다(`403`). 친구를 끊어도 이미 지정된 담당자는 유지됩니다. 활동 기록에는 담당자를 이름으로 남깁니다.

회원 탈퇴 시 내가 만든 할 일(댓글·활동 기록 포함)과 친구 관계는 삭제되고, 내가 담당자인 할 일은 담당자가 비워집니다. 다른 사람의 할 일에 남긴 댓글·활동 기록은 남고 작성자는 `null`("탈퇴한 사용자")이 됩니다.

할 일 데이터의 주요 필드는 다음과 같습니다.

```json
{
	"title": "주간 계획 세우기",
	"description": "이번 주 할 일 정리",
	"start_at": "2026-10-05T09:00",
	"end_at": "2026-10-05T17:00",
	"location": "집",
	"status": "planned",
	"tag": "work",
	"priority": "medium",
	"assignee_id": 2
}
```

`title`은 필수이며 1~100자입니다. `start_at`(시작 일시)과 `end_at`(마감 일시)은 요청·응답·DB에서 모두 필수이며 `null`을 허용하지 않습니다. 지원 형식은 `YYYY-MM-DD`, `YYYY-MM-DDTHH:MM`, `YYYY-MM-DDTHH:MM:SS`입니다. DB에는 시간대 없는 `TIMESTAMP`로 저장하며, 날짜만 보내면 시작 일시는 그날 0시, 종료 일시는 그날 23:59:59로 저장합니다. 응답은 `YYYY-MM-DDTHH:MM` 형식이고 초가 0이 아니면 `YYYY-MM-DDTHH:MM:SS` 형식입니다. 종료 일시는 시작 일시보다 앞설 수 없습니다. `status`는 `planned`, `in_progress`, `done`, `tag`는 `hangout`, `work`, `important`, `trip` 중 하나이며 태그는 생략할 수 있습니다. `priority`는 `low`, `medium`, `high` 중 하나입니다. ID와 작성자(`owner`)는 생성 시 서버가 정합니다. `assignee_id`는 가입한 사용자의 ID이며 없는 사용자면 `422`를 반환합니다. 응답에는 `owner`, `assignee` 사용자 정보(`id`, `username`, `display_name`)가 함께 들어 있습니다.

`PATCH`는 바꿀 필드만 보냅니다. 예: `{"status": "done"}`. `tag`와 `assignee_id`만 `null`로 지울 수 있고, 다른 필드에 `null`을 보내거나 알 수 없는 필드를 보내면 `422`를 반환합니다. 시작·종료 일시 중 하나만 보내면 저장된 나머지 값과 비교해 검증합니다. Swagger UI는 `/docs`에서 사용할 수 있습니다.

## 프로젝트 구조

```text
.
├── docker-compose.yml
├── fastapi-app/
│   ├── backend/
│   │   ├── __init__.py         # 백엔드 Python 패키지
│   │   ├── main.py             # 할 일·댓글·활동 기록 API와 프로덕션 정적 파일 제공
│   │   ├── auth.py             # 회원가입, 로그인(JWT), 내 정보, 회원 탈퇴 API
│   │   ├── friends.py          # 친구 요청·친구 목록 API
│   │   ├── database.py         # DB 연결, 테이블 정의(users, todos, comments, activities, friendships), 시작 시 마이그레이션 적용
│   │   └── migrations/         # Alembic 마이그레이션 (env.py, versions/)
│   ├── Dockerfile              # 프런트엔드 빌드 및 백엔드 이미지
│   ├── alembic.ini             # Alembic CLI 설정
│   ├── requirements.txt        # Python 의존성
│   ├── pyproject.toml          # 테스트 설정
│   ├── frontend/               # React + Vite 애플리케이션
│   └── tests/                  # API 및 배포 동작 테스트
```
