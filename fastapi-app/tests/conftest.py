import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--base-url",
        action="store",
        default=None,
    )


@pytest.fixture
def base_url(request):
    url = request.config.getoption("--base-url")
    if not url:
        pytest.fail("--base-url 옵션이 필요합니다. 예: pytest --base-url http://0.0.0.0:8000")
    return url.rstrip("/")