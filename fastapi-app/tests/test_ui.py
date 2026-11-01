# Playwright 로 배포된 React 화면을 실제 브라우저에서 테스트
# 실행 예: BASE_URL=http://localhost:5001 pytest tests/test_ui.py  (--headed 를 붙이면 브라우저 창이 보임)
import json
import uuid
from datetime import date, timedelta

import pytest
from playwright.sync_api import Page, expect


def unique(title):
    # 기존 데이터나 다른 테스트와 겹치지 않도록 제목 뒤에 랜덤 값을 붙임
    return f"{title} {uuid.uuid4().hex[:6]}"


@pytest.fixture(autouse=True)
def logged_in(page: Page, client):
    # API 로 만든 테스트 계정의 토큰을 미리 넣어 두어 로그인 화면을 건너뛴다
    page.add_init_script(f"window.localStorage.setItem('todo-token', {json.dumps(client.token)})")


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


def fill_period(modal, start, end):
    # 시작/종료 일시는 필수 입력
    modal.locator("input[type=datetime-local]").nth(0).fill(start)
    modal.locator("input[type=datetime-local]").nth(1).fill(end)


def checklist_item(page: Page, title):
    return page.locator(".checklist-item").filter(has_text=title)


def test_board_shows_three_columns(board):
    for label in ("예정", "진행중", "완료"):
        expect(board.get_by_role("heading", name=label, exact=True)).to_be_visible()


def test_add_card_via_modal(board, client, ui_cleanup):
    title = unique("UI 추가 테스트")
    ui_cleanup(title)

    column(board, "진행중").get_by_role("button", name="할일 추가").click()
    modal = board.locator(".modal-box")
    expect(modal.get_by_role("heading", name="새 할일 추가")).to_be_visible()
    modal.get_by_placeholder("할일 제목을 입력하세요").fill(title)
    modal.get_by_placeholder("할일에 대한 설명...").fill("Playwright 로 추가")
    fill_period(modal, f"{date.today()}T09:00", f"{date.today() + timedelta(days=1)}T18:00")
    modal.get_by_label("담당자").select_option(str(client.user["id"]))
    modal.locator("select").nth(0).select_option("work")
    modal.locator("select").nth(1).select_option("high")
    modal.get_by_role("button", name="저장").click()

    expect(modal).to_be_hidden()
    new_card = card(column(board, "진행중"), title)
    expect(new_card).to_contain_text("업무")
    expect(new_card).to_contain_text("High")
    expect(new_card).to_contain_text(client.user["display_name"])

    saved = next(t for t in client.get("/todos").json() if t["title"] == title)
    assert saved["status"] == "in_progress"
    assert saved["tag"] == "work"
    assert saved["priority"] == "high"
    assert saved["assignee"] == client.user


def test_cancel_modal_does_not_create(board, client):
    title = unique("UI 취소 테스트")

    column(board, "예정").get_by_role("button", name="할일 추가").click()
    board.get_by_placeholder("할일 제목을 입력하세요").fill(title)
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
    title_input = page.get_by_placeholder("할일 제목을 입력하세요")
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

    page.get_by_placeholder("할일 검색...").fill(keyword)

    expect(card(page, match["title"])).to_be_visible()
    expect(card(page, other["title"])).to_have_count(0)


def test_drag_card_to_done(page: Page, base_url, client, todo_factory):
    todo = todo_factory(unique("UI 드래그 테스트"), status="planned")
    page.goto(base_url)

    card(column(page, "예정"), todo["title"]).drag_to(column(page, "완료"))

    expect(card(column(page, "완료"), todo["title"])).to_be_visible()
    saved = next(t for t in client.get("/todos").json() if t["id"] == todo["id"])
    assert saved["status"] == "done"


def test_calendar_view_shows_dated_todo(page: Page, base_url, todo_factory):
    today = date.today().isoformat()
    dated = todo_factory(unique("달력 일정"), start_at=f"{today}T10:00", end_at=f"{today}T18:00")
    page.goto(base_url)

    page.locator(".view-sidebar").get_by_role("button", name="달력", exact=True).click()
    expect(page.get_by_role("region", name="할 일 달력")).to_be_visible()

    today_cell = page.locator(".calendar-day.is-today")
    expect(today_cell.get_by_role("button", name=dated["title"])).to_be_visible()

    # 보기 방식은 localStorage 에 저장되므로 새로고침해도 달력이 유지되어야 함
    page.reload()
    expect(page.get_by_role("region", name="할 일 달력")).to_be_visible()


def test_calendar_add_button_prefills_date(page: Page, base_url, client, ui_cleanup):
    today = date.today().isoformat()
    title = unique("달력 추가")
    ui_cleanup(title)
    page.goto(base_url)
    page.locator(".view-sidebar").get_by_role("button", name="달력", exact=True).click()

    page.get_by_role("button", name=f"{today}에 할일 추가").click()
    modal = page.locator(".modal-box")
    expect(modal.locator("input[type=datetime-local]").first).to_have_value(f"{today}T09:00")
    page.get_by_placeholder("할일 제목을 입력하세요").fill(title)
    modal.locator("input[type=datetime-local]").nth(1).fill(f"{today}T18:00")
    page.get_by_role("button", name="저장").click()

    expect(page.locator(".calendar-day.is-today")).to_contain_text(title)
    saved = next(t for t in client.get("/todos").json() if t["title"] == title)
    assert saved["start_at"] == f"{today}T09:00"


def test_add_requires_period(board, client):
    title = unique("UI 일시 누락")

    column(board, "예정").get_by_role("button", name="할일 추가").click()
    board.get_by_placeholder("할일 제목을 입력하세요").fill(title)
    board.get_by_role("button", name="저장").click()

    # 시작/종료 일시가 비어 있으면 저장되지 않고 모달이 그대로 남음
    expect(board.locator(".modal-box")).to_be_visible()
    assert all(t["title"] != title for t in client.get("/todos").json())


def test_checklist_shows_only_active_checklist_tags(page: Page, base_url, todo_factory):
    today = date.today()
    work = todo_factory(unique("체크리스트 업무"), tag="work")
    trip = todo_factory(unique("체크리스트 여행"), tag="trip")
    expired = todo_factory(
        unique("체크리스트 지난 일정"),
        tag="important",
        start_at=f"{today - timedelta(days=3)}T09:00",
        end_at=f"{today - timedelta(days=2)}T18:00",
    )
    page.goto(base_url)

    expect(checklist_item(page, work["title"])).to_be_visible()
    expect(checklist_item(page, trip["title"])).to_have_count(0)
    expect(checklist_item(page, expired["title"])).to_have_count(0)


def test_checklist_toggle_moves_between_done_and_in_progress(page: Page, base_url, client, todo_factory):
    todo = todo_factory(unique("체크리스트 토글"), tag="hangout", status="planned")
    page.goto(base_url)
    checkbox = checklist_item(page, todo["title"]).get_by_role("checkbox")

    # 체크 상태는 서버 저장이 끝난 뒤 바뀌므로 check() 대신 click() 후 상태를 기다림
    checkbox.click()
    expect(checkbox).to_be_checked()
    expect(card(column(page, "완료"), todo["title"])).to_be_visible()
    assert next(t for t in client.get("/todos").json() if t["id"] == todo["id"])["status"] == "done"

    # 체크를 풀면 예정이 아니라 진행중으로 돌아감
    checkbox.click()
    expect(checkbox).not_to_be_checked()
    expect(card(column(page, "진행중"), todo["title"])).to_be_visible()
    assert next(t for t in client.get("/todos").json() if t["id"] == todo["id"])["status"] == "in_progress"


def test_login_screen_without_token(browser, base_url, client):
    page = browser.new_page()                       # 토큰을 넣지 않은 새 페이지
    page.goto(base_url)
    expect(page.get_by_role("region", name="로그인")).to_be_visible()
    expect(page.get_by_role("heading", name="Todo-List")).to_be_visible()
    page.close()


def test_signup_logout_and_delete_account(browser, base_url, client):
    page = browser.new_page()
    page.goto(base_url)
    username = f"ui_{uuid.uuid4().hex[:10]}"
    page.get_by_role("tab", name="회원가입").click()
    page.get_by_label("아이디").fill(username)
    page.get_by_label("이름").fill("UI 가입자")
    page.get_by_label("비밀번호").fill("password123")
    page.get_by_role("button", name="가입하고 시작하기").click()

    expect(page.get_by_role("heading", name="예정", exact=True)).to_be_visible()
    expect(page.locator(".user-menu")).to_contain_text("UI 가입자")

    page.get_by_role("button", name="로그아웃").click()
    expect(page.get_by_role("region", name="로그인")).to_be_visible()

    # 다시 로그인해서 탈퇴 (테스트 계정을 남기지 않는다)
    page.get_by_label("아이디").fill(username)
    page.get_by_label("비밀번호").fill("password123")
    page.get_by_role("button", name="로그인").click()
    page.get_by_role("button", name="회원 탈퇴").click()
    modal = page.locator(".modal-box")
    modal.get_by_label("비밀번호 확인").fill("wrong-password")
    modal.get_by_role("button", name="탈퇴하기").click()
    expect(modal.get_by_role("alert")).to_have_text("비밀번호가 올바르지 않습니다.")
    modal.get_by_label("비밀번호 확인").fill("password123")
    modal.get_by_role("button", name="탈퇴하기").click()
    expect(page.get_by_role("region", name="로그인")).to_be_visible()

    page.get_by_label("아이디").fill(username)
    page.get_by_label("비밀번호").fill("password123")
    page.get_by_role("button", name="로그인").click()
    expect(page.get_by_role("alert")).to_have_text("아이디 또는 비밀번호가 올바르지 않습니다.")
    page.close()


def test_wrong_password_shows_error(browser, base_url, client):
    page = browser.new_page()
    page.goto(base_url)
    page.get_by_label("아이디").fill(client.user["username"])
    page.get_by_label("비밀번호").fill("wrong-password")
    page.get_by_role("button", name="로그인").click()
    expect(page.get_by_role("alert")).to_have_text("아이디 또는 비밀번호가 올바르지 않습니다.")
    page.close()


def test_comment_and_activity_in_modal(page: Page, base_url, todo_factory):
    todo = todo_factory(unique("UI 댓글"))
    page.goto(base_url)
    target = card(page, todo["title"])
    target.hover()
    target.get_by_title("편집").click()

    modal = page.locator(".modal-box")
    modal.get_by_placeholder("댓글을 입력하세요").fill("UI 에서 남긴 댓글")
    modal.get_by_role("button", name="등록").click()
    expect(modal.locator(".comment-item")).to_contain_text("UI 에서 남긴 댓글")

    modal.get_by_role("tab", name="활동 기록").click()
    expect(modal.locator(".activity-item")).to_contain_text("할 일을 만들었습니다")


def test_my_todos_filter(page: Page, base_url, client, todo_factory):
    mine = todo_factory(unique("내가 담당"), assignee_id=client.user["id"])
    unassigned = todo_factory(unique("담당자 없음"))
    page.goto(base_url)
    expect(card(page, unassigned["title"])).to_be_visible()

    page.get_by_role("button", name="내 할 일").click()

    expect(card(page, mine["title"])).to_be_visible()
    expect(card(page, unassigned["title"])).to_have_count(0)


def test_accept_friend_request_and_assign(page: Page, base_url, client, other_account, todo_factory):
    # 다른 계정이 나에게 친구 요청을 보낸다
    friend = {"Authorization": f"Bearer {other_account['token']}"}
    assert client.post("/friends/requests", json={"username": client.user["username"]}, headers=friend).status_code == 201
    todo = todo_factory(unique("친구에게 맡김"))
    page.goto(base_url)

    page.get_by_role("button", name="친구").click()
    modal = page.locator(".modal-box")
    received = modal.get_by_role("region", name="받은 친구 요청")
    expect(received).to_contain_text(other_account["username"])
    received.get_by_role("button", name="수락").click()
    expect(modal.get_by_role("region", name="친구 목록")).to_contain_text(other_account["display_name"])
    modal.get_by_role("button", name="닫기").click()

    target = card(page, todo["title"])
    target.hover()
    target.get_by_title("편집").click()
    modal = page.locator(".modal-box")
    modal.get_by_label("담당자").select_option(str(other_account["id"]))
    modal.get_by_role("button", name="저장").click()

    expect(modal).to_be_hidden()
    expect(card(page, todo["title"])).to_contain_text(other_account["display_name"])


def test_locked_account_shows_message(browser, base_url, client, other_account):
    for _ in range(10):                                  # 비밀번호를 10번 틀리면 잠긴다
        client.post("/auth/login", data={"username": other_account["username"], "password": "wrong-password"})
    page = browser.new_page()
    page.goto(base_url)
    page.get_by_label("아이디").fill(other_account["username"])
    page.get_by_label("비밀번호").fill(other_account["password"])
    page.get_by_role("button", name="로그인").click()
    expect(page.get_by_role("alert")).to_have_text("로그인 시도가 너무 많습니다. 15분 후에 다시 시도하세요.")
    page.close()
