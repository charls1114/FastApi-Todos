# fastapi-app/tests/conftest.py
import base64
import os
import time

import httpx2
import pytest
import pytest_html

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
            if http.get("/todos").status_code == 200:
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
        yield c


@pytest.fixture
def todo_factory(client):
    created_ids = []

    def create_todo(title, **fields):
        payload = {"title": title, "description": "배포 테스트 항목", **fields}
        response = client.post("/todos", json=payload)
        assert response.status_code == 201
        todo = response.json()
        created_ids.append(todo["id"])
        return todo

    yield create_todo

    for todo_id in created_ids:
        response = client.delete(f"/todos/{todo_id}")
        assert response.status_code in (204, 404)
