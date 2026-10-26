"""postToolUse: 도구 사용 감사 로그(JSONL). 인수·결과 본문은 기록하지 않는다."""
import json
import time

from _hooklib import REPO_ROOT, emit, read_event, tool_name

LOG_DIR = REPO_ROOT / ".github" / "hooks" / "logs"


def main() -> None:
    event = read_event()
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "session": event.get("sessionId") or event.get("session_id"),
            "tool": tool_name(event),
        }
        with open(LOG_DIR / "tool-use.jsonl", "a", encoding="utf-8") as log:
            log.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass  # 감사 로그 실패가 에이전트 작업을 막지 않도록 한다.
    emit({})


if __name__ == "__main__":
    main()
