# FastApi-Todos 프로젝트 지침

이 저장소는 FastAPI(백엔드)와 React(프런트엔드)로 만든 칸반 방식 할 일 관리 앱이다. 모든 응답, 커밋 메시지, PR 본문, 코드 주석은 **한국어**로 작성한다.

## 구조와 기술 스택
- `fastapi-app/backend/main.py`: FastAPI 라우트, Pydantic 모델(`TodoIn`, `TodoItem`), 프로덕션 정적 파일 제공
- `fastapi-app/backend/database.py`: SQLAlchemy 2.0 모델(`Todo`), DB 연결, `init_db()`
- `fastapi-app/frontend/src/`: React 19 + Vite 8 + Tailwind CSS 4 (`App.jsx`, `api.js`, `utils.js`, `index.css`)
- `fastapi-app/tests/`: pytest API 테스트, 배포 테스트, Playwright UI 테스트
- 저장소: PostgreSQL 17 (Psycopg 3), 테스트 기본값은 임시 SQLite
- Python 3.13, Node.js 22

## 빌드·테스트 명령 (항상 이 명령으로 검증한다)
- 백엔드 테스트: `cd fastapi-app && pytest tests/test_main.py tests/test_database.py`
- PostgreSQL 검증: `TEST_DATABASE_URL`을 설정한 뒤 같은 명령 실행
- 프런트엔드: `cd fastapi-app/frontend && npm ci && npm run lint && npm run build`
- UI 테스트: 서버 실행 후 `BASE_URL=http://localhost:5001 pytest tests/test_ui.py`
- 개발 서버: `uvicorn backend.main:app --reload --port 8000` / `npm run dev`

## 공통 규칙
- API 계약(`README.md`의 API 표와 필드 설명)을 바꾸면 README도 같은 PR에서 갱신한다.
- `status`·`tag`·`priority` 허용값은 세 곳이 항상 일치해야 한다: `main.py`의 `Literal`, `database.py`의 `CheckConstraint`, `frontend/src/utils.js`의 상수.
- 날짜·시간은 `YYYY-MM-DD`, `YYYY-MM-DDTHH:MM`, `YYYY-MM-DDTHH:MM:SS` 문자열이며 타임존이 없다.
- 마이그레이션 도구가 없다. 컬럼 추가·변경이 필요하면 구현 전에 사람에게 확인받는다.
- 버그 수정은 실패하는 테스트를 먼저 추가하고 고친다.
- 새 의존성 추가는 이유를 PR 본문에 적는다.

## 보안·운영 금지 사항
- `.env` 파일을 읽거나 만들거나 커밋하지 않는다. 예시 값은 `.env.example`만 사용한다.
- 비밀번호·토큰(`sonar.token` 포함)을 코드나 설정 파일에 쓰지 않는다.
- `docker compose down -v`, `docker volume rm` 등 데이터 볼륨을 지우는 명령을 실행하지 않는다.
- Dockerfile의 non-root 실행(`appuser`)과 `docker-compose.yml`의 `cap_drop`, `no-new-privileges` 설정을 약화하지 않는다.

## 커밋·PR 규칙
- 커밋 메시지: `feat: …`, `fix: …`, `refactor: …`, `test: …`, `docs: …`, `chore: …` 접두어 + 한국어 요약
- PR 본문: 변경 요약, 검증한 명령과 결과, 남은 위험을 적는다.
- 릴리즈는 `.github/RELEASE_TEMPLATE.md` 양식을 따른다.

## 커스텀 에이전트
작업 유형에 맞는 에이전트를 사용한다: `Backend Dev`(API·DB), `Frontend Dev`(React UI), `QA Bug Fixer`(재현·테스트·버그 수정), `Refactorer`(동작 보존 구조 개선), `Todo Orchestrator`(VS Code에서 여러 에이전트 조율).
