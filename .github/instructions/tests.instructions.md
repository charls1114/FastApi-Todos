---
applyTo: "fastapi-app/tests/**/*.py"
---
# 테스트 작성 규칙

- API 테스트는 `conftest.py`의 `api_client` fixture를 사용한다. 기본은 임시 SQLite이며 `TEST_DATABASE_URL`이 있으면 격리된 PostgreSQL 스키마를 쓴다.
- 시작·종료 일시는 필수다. 테스트 데이터에는 `PERIOD` 상수나 명시적 `start_at`/`end_at`을 넣는다.
- 경계값은 `pytest.mark.parametrize`로 묶는다.
- 버그 수정 테스트 이름은 `test_<동작>_<기대결과>` 형식으로 쓴다. 예: `test_create_todo_invalid_calendar_date_returns_422`
- 배포·UI 테스트(`test_deployed.py`, `test_ui.py`)는 `BASE_URL`이 필요하므로 기본 테스트 명령에 섞지 않는다.
- UI 테스트에서 만든 데이터는 `ui_cleanup`/`todo_factory`로 정리한다.
