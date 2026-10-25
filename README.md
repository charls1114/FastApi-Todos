# FastApi-Todos

FastAPI와 React로 만든 칸반 방식의 할 일 관리 웹 애플리케이션입니다. 할 일을 예정, 진행 중, 완료 상태로 나누어 관리하고, 카드 드래그 앤 드롭으로 작업 상태를 변경할 수 있습니다.

## 주요 기능

- 칸반 보드에서 할 일 추가, 수정, 삭제 및 상태 변경
- 내비게이션 버튼으로 칸반 보드와 월간 달력 보기 전환
- 시작일·종료일·마감일에 따른 달력 표시 및 날짜별 할 일 추가
- 제목과 설명으로 카드 검색
- 설명, 시작·마감 일시, 장소, 태그, 우선순위, 담당자 관리
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
# .env의 POSTGRES_PASSWORD를 변경한 뒤 실행합니다.
docker compose up --build -d
```

브라우저에서 [http://localhost:5001](http://localhost:5001)을 열면 애플리케이션을 사용할 수 있습니다. API 문서는 [http://localhost:5001/docs](http://localhost:5001/docs), 상태 확인은 [http://localhost:5001/health](http://localhost:5001/health)에서 확인할 수 있습니다.

PowerShell에서는 `Copy-Item .env.example .env`로 설정 파일을 복사합니다. API는 PostgreSQL의 준비 상태를 확인한 후 시작하며, 최초 실행 시 `todos` 테이블을 생성합니다. 이후 스키마 변경에는 별도의 마이그레이션이 필요합니다.

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
pytest tests/test_main.py tests/test_database.py
```

기본 API 테스트는 임시 SQLite DB를 사용합니다. 실제 PostgreSQL 검증은 `TEST_DATABASE_URL`을 별도의 테스트 DB 연결 문자열로 설정한 뒤 같은 명령을 실행합니다. 각 테스트는 임의의 전용 스키마를 생성하고 종료 시 제거하므로 테스트 계정에 스키마 생성 권한이 필요합니다. 배포 및 UI 테스트는 기존처럼 `BASE_URL`을 지정한 실행 서버를 대상으로 별도 실행합니다.

## API

모든 할 일 데이터는 `/todos` 경로에서 JSON으로 주고받습니다.

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| `GET` | `/todos` | 할 일 목록 조회 |
| `POST` | `/todos` | 할 일 생성 (성공 시 `201`) |
| `PUT` | `/todos/{todo_id}` | 할 일 전체 수정 |
| `DELETE` | `/todos/{todo_id}` | 할 일 삭제 (성공 시 `204`) |
| `GET` | `/health` | 서비스 상태 확인 |

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
	"assignee": "담당자"
}
```

`title`은 필수이며 1~100자입니다. `start_at`(시작 일시)과 `end_at`(마감 일시)은 요청·응답·DB에서 모두 필수이며 `null`을 허용하지 않습니다. 지원 형식은 `YYYY-MM-DD`, `YYYY-MM-DDTHH:MM`, `YYYY-MM-DDTHH:MM:SS`입니다. 종료 일시는 시작 일시보다 앞설 수 없으며 날짜만 지정한 종료일은 해당 날짜의 끝으로 비교합니다. `status`는 `planned`, `in_progress`, `done`, `tag`는 `hangout`, `work`, `important`, `trip` 중 하나이며 태그는 생략할 수 있습니다. `priority`는 `low`, `medium`, `high` 중 하나입니다. ID는 생성 시 서버가 부여합니다. Swagger UI는 `/docs`에서 사용할 수 있습니다.

## 프로젝트 구조

```text
.
├── docker-compose.yml
├── fastapi-app/
│   ├── backend/
│   │   ├── __init__.py         # 백엔드 Python 패키지
│   │   ├── main.py             # FastAPI API와 프로덕션 정적 파일 제공
│   │   └── database.py         # DB 연결 및 todos 테이블 정의
│   ├── Dockerfile              # 프런트엔드 빌드 및 백엔드 이미지
│   ├── requirements.txt        # Python 의존성
│   ├── pyproject.toml          # 테스트 설정
│   ├── frontend/               # React + Vite 애플리케이션
│   └── tests/                  # API 및 배포 동작 테스트
```
