# Playwright 로 배포된 React 화면을 실제 브라우저에서 테스트
# 실행 예: BASE_URL=http://localhost:5001 pytest tests/test_ui.py  (--headed 를 붙이면 브라우저 창이 보임)
import uuid
from datetime import date

import pytest
from playwright.sync_api import Page, expect


def unique(title):
    # 기존 데이터나 다른 테스트와 겹치지 않도록 제목 뒤에 랜덤 값을 붙임
    return f"{title} {uuid.uuid4().hex[:6]}"


@pytest.fixture
def board(page: Page, base_url, client):
    # client fixture 가 컨테이너 준비를 기다린 뒤 보드 화면을 연다
    page.goto(base_url)
    expect(page.get_by_role("heading", name="Todo-List")).to_be_visible()
    return page


@pytest.fixture
def ui_cleanup(client):
    # 화면에서 만든 카드는 id 를 모르므로 제목으로 찾아서 정리
    titles = []
    yield titles.append
    for todo in client.get("/todos").json():
        if todo["title"] in titles:
            client.delete(f"/todos/{todo['id']}")


def column(page: Page, label):
    return page.locator("main > div").filter(has=page.get_by_role("heading", name=label, exact=True))


def card(scope, title):
    return scope.locator(".card-drag").filter(has_text=title)


def test_board_shows_three_columns(board):
    for label in ("예정", "진행중", "완료"):
        expect(board.get_by_role("heading", name=label, exact=True)).to_be_visible()


def test_add_card_via_modal(board, client, ui_cleanup):
    title = unique("UI 추가 테스트")
    ui_cleanup(title)

    column(board, "진행중").get_by_role("button", name="카드 추가").click()
    modal = board.locator(".modal-box")
    expect(modal.get_by_role("heading", name="새 카드 추가")).to_be_visible()
    modal.get_by_placeholder("카드 제목을 입력하세요").fill(title)
    modal.get_by_placeholder("작업에 대한 설명...").fill("Playwright 로 추가")
    modal.get_by_placeholder("담당자 이름").fill("Hana")
    modal.locator("select").nth(0).select_option("work")
    modal.locator("select").nth(1).select_option("high")
    modal.get_by_role("button", name="저장").click()

    expect(modal).to_be_hidden()
    new_card = card(column(board, "진행중"), title)
    expect(new_card).to_contain_text("업무")
    expect(new_card).to_contain_text("High")
    expect(new_card).to_contain_text("Hana")

    saved = next(t for t in client.get("/todos").json() if t["title"] == title)
    assert saved["status"] == "in_progress"
    assert saved["tag"] == "work"
    assert saved["priority"] == "high"


def test_cancel_modal_does_not_create(board, client):
    title = unique("UI 취소 테스트")

    column(board, "예정").get_by_role("button", name="카드 추가").click()
    board.get_by_placeholder("카드 제목을 입력하세요").fill(title)
    board.get_by_role("button", name="취소").click()

    expect(board.locator(".modal-box")).to_be_hidden()
    expect(card(board, title)).to_have_count(0)
    assert all(t["title"] != title for t in client.get("/todos").json())


def test_edit_card(page: Page, base_url, client, todo_factory, ui_cleanup):
    todo = todo_factory(unique("UI 수정 전"))
    new_title = unique("UI 수정 후")
    ui_cleanup(new_title)
    page.goto(base_url)

    target = card(page, todo["title"])
    target.hover()
    target.get_by_title("편집").click()
    title_input = page.get_by_placeholder("카드 제목을 입력하세요")
    expect(title_input).to_have_value(todo["title"])
    title_input.fill(new_title)
    page.get_by_role("button", name="저장").click()

    expect(card(page, new_title)).to_be_visible()
    expect(card(page, todo["title"])).to_have_count(0)
    saved = next(t for t in client.get("/todos").json() if t["id"] == todo["id"])
    assert saved["title"] == new_title


def test_delete_card_after_confirm(page: Page, base_url, client, todo_factory):
    todo = todo_factory(unique("UI 삭제 테스트"))
    page.goto(base_url)

    page.once("dialog", lambda dialog: dialog.accept())  # "정말 삭제할까요?" 확인
    target = card(page, todo["title"])
    target.hover()
    target.get_by_title("삭제").click()

    expect(card(page, todo["title"])).to_have_count(0)
    assert all(t["id"] != todo["id"] for t in client.get("/todos").json())


def test_delete_card_dismissed_keeps_card(page: Page, base_url, client, todo_factory):
    todo = todo_factory(unique("UI 삭제 취소"))
    page.goto(base_url)

    page.once("dialog", lambda dialog: dialog.dismiss())
    target = card(page, todo["title"])
    target.hover()
    target.get_by_title("삭제").click()

    expect(target).to_be_visible()
    assert any(t["id"] == todo["id"] for t in client.get("/todos").json())


def test_search_filters_cards(page: Page, base_url, todo_factory):
    keyword = uuid.uuid4().hex[:8]
    match = todo_factory(f"검색 대상 {keyword}")
    other = todo_factory(unique("검색 제외"))
    page.goto(base_url)
    expect(card(page, other["title"])).to_be_visible()

    page.get_by_placeholder("카드 검색...").fill(keyword)

    expect(card(page, match["title"])).to_be_visible()
    expect(card(page, other["title"])).to_have_count(0)


def test_drag_card_to_done(page: Page, base_url, client, todo_factory):
    todo = todo_factory(unique("UI 드래그 테스트"), status="planned")
    page.goto(base_url)

    card(column(page, "예정"), todo["title"]).drag_to(column(page, "완료"))

    expect(card(column(page, "완료"), todo["title"])).to_be_visible()
    saved = next(t for t in client.get("/todos").json() if t["id"] == todo["id"])
    assert saved["status"] == "done"


def test_calendar_view_shows_dated_and_undated(page: Page, base_url, todo_factory):
    today = date.today().isoformat()
    dated = todo_factory(unique("달력 일정"), start_at=f"{today}T10:00", end_at=f"{today}T18:00")
    undated = todo_factory(unique("달력 미지정"))
    page.goto(base_url)

    page.get_by_role("button", name="달력", exact=True).click()
    expect(page.get_by_role("region", name="할 일 달력")).to_be_visible()

    today_cell = page.locator(".calendar-day.is-today")
    expect(today_cell.get_by_role("button", name=dated["title"])).to_be_visible()
    expect(page.locator(".calendar-undated")).to_contain_text(undated["title"])

    # 보기 방식은 localStorage 에 저장되므로 새로고침해도 달력이 유지되어야 함
    page.reload()
    expect(page.get_by_role("region", name="할 일 달력")).to_be_visible()


def test_calendar_add_button_prefills_date(page: Page, base_url, client, ui_cleanup):
    today = date.today().isoformat()
    title = unique("달력 추가")
    ui_cleanup(title)
    page.goto(base_url)
    page.get_by_role("button", name="달력", exact=True).click()

    page.get_by_role("button", name=f"{today}에 할 일 추가").click()
    expect(page.locator(".modal-box input[type=datetime-local]").first).to_have_value(f"{today}T09:00")
    page.get_by_placeholder("카드 제목을 입력하세요").fill(title)
    page.get_by_role("button", name="저장").click()

    expect(page.locator(".calendar-day.is-today")).to_contain_text(title)
    saved = next(t for t in client.get("/todos").json() if t["title"] == title)
    assert saved["start_at"] == f"{today}T09:00"
