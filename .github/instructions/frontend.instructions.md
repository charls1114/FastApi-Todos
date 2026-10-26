---
applyTo: "fastapi-app/frontend/**"
---
# 프런트엔드(React 19 + Vite 8 + Tailwind 4) 작성 규칙

- 함수 컴포넌트와 훅만 사용한다. 클래스 컴포넌트를 추가하지 않는다.
- 서버 통신은 `src/api.js`의 함수만 사용한다. 컴포넌트에서 `fetch`를 직접 호출하지 않는다.
- 상태값·라벨·색상 상수는 `src/utils.js`에 둔다(`STATUSES`, `TAG_LABELS`, `PRIORITY_LABELS` 등).
- 색상·폰트는 `src/index.css`의 `@theme` 토큰(`--color-todo`, `--color-progress`, `--color-done` 등)을 사용하고 임의 hex 값을 새로 만들지 않는다.
- 화면 문구는 한국어로 쓴다. Playwright 테스트가 `예정`, `진행중`, `완료`, `할일 추가` 같은 문구와 role로 요소를 찾으므로 바꾸면 `tests/test_ui.py`도 함께 수정한다.
- 모달은 `<dialog>`와 Escape 닫기 등 기존 접근성 동작을 유지한다.
- 변경 후 `npm run lint`(oxlint)와 `npm run build`가 통과해야 한다.
