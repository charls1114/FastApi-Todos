---
applyTo: "fastapi-app/backend/**/*.py"
---
# 백엔드(FastAPI) 작성 규칙

- 라우트 함수는 동기 `def`와 `db: Session = Depends(get_db)` 패턴을 유지한다.
- 요청 모델은 `TodoIn`, 응답 모델은 `TodoItem`(`from_attributes=True`)을 재사용한다. 응답에 ORM 객체를 그대로 반환하지 않고 `TodoItem.model_validate()`를 거친다.
- 없는 리소스는 `find_todo()`로 조회해 `HTTPException(404, "To-Do item not found")`를 일관되게 반환한다.
- 상태 코드: 생성 `201`, 삭제 `204`, 검증 실패는 Pydantic 기본 `422`에 맡긴다.
- 허용값(`Status`, `Tag`, `Priority`)을 바꾸면 `database.py`의 `CheckConstraint`와 `frontend/src/utils.js`도 함께 바꾼다.
- 날짜 검증은 정규식만으로 끝내지 말고 실제 달력·시각으로 해석 가능한지 확인한다.
- 정적 파일 마운트(`app.mount("/", ...)`)는 항상 모든 API 라우트 정의 **뒤**에 둔다. 앞에 두면 새 라우트가 가려진다.
- DB 세션은 `get_db()`가 닫는다. 라우트 안에서 세션을 직접 만들지 않는다.
