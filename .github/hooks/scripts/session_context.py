"""sessionStart: 세션 시작 시 현재 브랜치와 작업 트리 상태, 검증 명령을 컨텍스트로 주입한다."""
import subprocess

from _hooklib import REPO_ROOT, emit, read_event


def git(*args: str) -> str:
    try:
        out = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=5)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def main() -> None:
    read_event()
    branch = git("rev-parse", "--abbrev-ref", "HEAD") or "(알 수 없음)"
    changed = git("status", "--porcelain").splitlines()
    changed_summary = ", ".join(line[3:] for line in changed[:10]) or "없음"
    context = (
        f"[FastApi-Todos 세션 정보] 현재 브랜치: {branch} / 커밋되지 않은 변경: {changed_summary}\n"
        "작업 완료 전 품질 게이트(agentStop Hook)가 백엔드 pytest와 프런트엔드 oxlint를 자동 실행한다. "
        "실패하면 작업을 끝낼 수 없으니 먼저 직접 실행해 확인하라: "
        "`cd fastapi-app && python -m pytest tests/test_main.py tests/test_database.py -q`, "
        "`cd fastapi-app/frontend && npm run lint`."
    )
    emit({
        "additionalContext": context,
        "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context},
    })


if __name__ == "__main__":
    main()
