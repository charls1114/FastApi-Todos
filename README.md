# FastApi-Todos

FastAPI와 React로 만든 칸반 방식의 할 일 관리 웹 애플리케이션입니다. 할 일을 예정, 진행 중, 완료 상태로 나누어 관리하고, 카드 드래그 앤 드롭으로 작업 상태를 변경할 수 있습니다.

## 주요 기능

- 칸반 보드에서 할 일 추가, 수정, 삭제 및 상태 변경
- 내비게이션 버튼으로 칸반 보드와 월간 달력 보기 전환
- 시작일·종료일·마감일에 따른 달력 표시 및 날짜별 할 일 추가
- 날짜가 지정되지 않은 할 일도 달력의 별도 목록에서 확인
- 제목과 설명으로 카드 검색
- 설명, 시작·마감 일시, 장소, 태그, 우선순위, 담당자 관리
- 전체 할 일 중 완료된 항목 수와 진행률 표시
- 마감일이 지난 항목 표시
- JSON 파일 기반 데이터 저장 및 Docker named volume을 통한 데이터 유지
- FastAPI의 OpenAPI 문서 제공

## 기술 스택

- 프런트엔드: React 19, Vite 8, Tailwind CSS 4
- 백엔드: Python 3.13, FastAPI, Uvicorn
- 저장소: `fastapi-app/todo.json` (JSON 파일)
- 배포: Docker, Docker Compose, 멀티 스테이지 이미지 빌드

## 빠른 시작: Docker Compose

Docker와 Docker Compose가 설치된 환경에서 저장소 루트에서 실행합니다.

```bash
docker compose up --build -d
```

브라우저에서 [http://localhost:5001](http://localhost:5001)을 열면 애플리케이션을 사용할 수 있습니다. API 문서는 [http://localhost:5001/docs](http://localhost:5001/docs), 상태 확인은 [http://localhost:5001/health](http://localhost:5001/health)에서 확인할 수 있습니다.

할 일 데이터는 Docker named volume `fastapi-todos_todo-data`에 저장되므로 컨테이너를 다시 만들어도 유지됩니다. 최초 volume을 만들 때 기존 `fastapi-app/todo.json`의 데이터가 volume으로 복사됩니다. `docker compose down`은 volume을 보존하며, 데이터를 포함해 완전히 제거하려면 `docker compose down -v`를 실행합니다.

```bash
docker compose down
```

## 로컬 개발

백엔드와 프런트엔드는 각각 별도 터미널에서 실행합니다. Python 3.13 이상과 Node.js 22 이상이 필요합니다.

### 백엔드

저장소 루트에서:

```bash
cd fastapi-app
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

개발 API는 `http://localhost:8000`에서 실행됩니다.

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
pytest
```

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

`title`은 필수이며 1~100자입니다. `start_at`은 시작 일시, `end_at`은 마감 일시이며 `YYYY-MM-DDTHH:MM` 형식입니다. `status`는 `planned`, `in_progress`, `done`, `tag`는 `hangout`, `work`, `important`, `trip` 중 하나이며 태그는 생략할 수 있습니다. `priority`는 `low`, `medium`, `high` 중 하나입니다. ID는 생성 시 서버가 부여합니다. 구버전 데이터의 `due_date`는 기존 마감 날짜를 보존해 `end_at`으로 자동 변환됩니다. Swagger UI는 `/docs`에서 사용할 수 있습니다.

## 프로젝트 구조

```text
.
├── docker-compose.yml
├── fastapi-app/
│   ├── main.py                 # FastAPI API와 프로덕션 정적 파일 제공
│   ├── todo.json               # 할 일 데이터
│   ├── Dockerfile              # 프런트엔드 빌드 및 백엔드 이미지
│   ├── frontend/               # React + Vite 애플리케이션
│   └── tests/                  # API 및 배포 동작 테스트
```