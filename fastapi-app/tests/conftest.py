# fastapi-app/tests/conftest.py
import base64
import os
import time
import uuid
from datetime import date, timedelta

import httpx2
import pytest
import pytest_html


@pytest.fixture
def empty_db(tmp_path, monkeypatch):
    """Use a temporary SQLite file, or an isolated PostgreSQL schema when configured (no tables yet)."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from backend import database

    url = os.environ.get("TEST_DATABASE_URL")
    admin_engine = None
    if url:
        admin_engine = create_engine(url)
        schema = "test_" + uuid.uuid4().hex
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    else:
        engine = create_engine(f"sqlite:///{tmp_path / 'todos.db'}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine))
    try:
        yield engine
    finally:
        engine.dispose()
        if admin_engine is not None:
            with admin_engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin_engine.dispose()


@pytest.fixture
def todo_db(empty_db):
    from backend import database

    database.init_db()   # 마이그레이션을 head 까지 적용
    return empty_db


@pytest.fixture
def api_client(todo_db):
    from fastapi.testclient import TestClient
    from backend.main import app

    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture
def login(api_client):
    """회원가입 후 로그인한 TestClient 를 돌려준다. client.user 에 사용자 정보가 들어 있다."""
    from fastapi.testclient import TestClient
    from backend.main import app

    def login(username="alice", display_name=None, password="password123"):
        response = api_client.post(
            "/auth/register",
            json={"username": username, "display_name": display_name or username.title(), "password": password},
        )
        assert response.status_code == 201
        token = api_client.post("/auth/login", data={"username": username, "password": password}).json()
        client = TestClient(app, headers={"Authorization": f"Bearer {token['access_token']}"})
        client.user = response.json()
        return client

    return login


@pytest.fixture(scope="session")
def base_url():
    # pytest-playwright(pytest-base-url)의 autouse fixture 가 모든 테스트에서 base_url 을 요청하므로
    # 여기서 실패시키면 test_main.py 까지 실패함 → 값이 없으면 None 을 돌려주고 검사는 client 에서 함
    value = os.environ.get("BASE_URL")
    return value.rstrip("/") if value else None


UI_REPORT = "reports/ui-report.html"


@pytest.hookimpl(tryfirst=True)  # pytest-html 이 보고서 경로를 읽기 전에 실행돼야 함
def pytest_configure(config):
    # UI 테스트를 실행하면 --html 옵션을 따로 주지 않아도 보고서를 만든다
    running_ui = any("test_ui" in arg for arg in config.args)
    if running_ui and not config.getoption("htmlpath"):
        config.option.htmlpath = str(config.rootpath / UI_REPORT)
        config.option.self_contained_html = True  # 스크린샷까지 html 파일 하나에 담음


def pytest_html_report_title(report):
    report.title = "Todo-List UI 테스트 보고서"


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    # UI 테스트가 실패하면 그 순간의 브라우저 화면을 보고서에 첨부
    outcome = yield
    report = outcome.get_result()
    page = item.funcargs.get("page")
    if report.when == "call" and report.failed and page:
        screenshot = base64.b64encode(page.screenshot(full_page=True)).decode()
        report.extras = [*getattr(report, "extras", []), pytest_html.extras.png(screenshot, "실패 화면")]


def wait_until_up(http, base_url, seconds=30):
    # 배포 직후에는 컨테이너가 아직 뜨는 중일 수 있으므로 응답이 올 때까지 기다림
    for _ in range(seconds):
        try:
            if http.get("/health").status_code == 200:
                return
        except httpx2.TransportError:  # 연결 거부, 타임아웃 등
            pass
        time.sleep(1)
    pytest.fail(f"{base_url} 에 접속할 수 없음 (컨테이너 실행 여부, 포트, 방화벽 확인)")


@pytest.fixture(scope="session")
def client(base_url):
    if not base_url:
        pytest.fail("BASE_URL 환경변수가 필요합니다.")
    with httpx2.Client(base_url=base_url, timeout=10) as c:
        wait_until_up(c, base_url)  # 컨테이너가 준비될 때까지 대기
        # 실행할 때마다 새 테스트 계정을 만들어 로그인한다 (다른 사용자의 데이터와 섞이지 않음)
        user = {"username": f"e2e_{uuid.uuid4().hex[:12]}", "display_name": "E2E 테스트", "password": uuid.uuid4().hex}
        response = c.post("/auth/register", json=user)
        assert response.status_code == 201, response.text
        token = c.post("/auth/login", data={"username": user["username"], "password": user["password"]}).json()
        c.headers["Authorization"] = f"Bearer {token['access_token']}"
        c.user = token["user"]
        c.token = token["access_token"]
        yield c


@pytest.fixture
def todo_factory(client):
    created_ids = []

    def create_todo(title, **fields):
        # 시작/종료 일시는 필수 — 기본값은 체크리스트에서 사라지지 않도록 오늘~내일로 둔다
        period = {"start_at": f"{date.today()}T00:00", "end_at": f"{date.today() + timedelta(days=1)}T23:59"}
        payload = {"title": title, "description": "배포 테스트 항목", **period, **fields}
        response = client.post("/todos", json=payload)
        assert response.status_code == 201
        todo = response.json()
        created_ids.append(todo["id"])
        return todo

    yield create_todo

    for todo_id in created_ids:
        response = client.delete(f"/todos/{todo_id}")
        assert response.status_code in (204, 404)
