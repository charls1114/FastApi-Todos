# fastapi-app/tests/conftest.py
import os
import pytest

@pytest.fixture(scope="session")
def base_url():
    value = os.environ.get("BASE_URL")
    if not value:
        pytest.fail("BASE_URL 환경변수가 필요합니다.")
    return value.rstrip("/")