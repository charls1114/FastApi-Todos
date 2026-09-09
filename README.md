# FastApi-Todos

간단한 Todo API와 DevOps 실습용 기본 설정입니다.

## 실행 방법

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## 테스트

```bash
pytest
```

## Docker

```bash
docker build -t fastapi-todos .
docker run --rm -p 8000:8000 fastapi-todos
```