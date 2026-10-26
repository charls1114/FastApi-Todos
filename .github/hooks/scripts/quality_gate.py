"""agentStop: 품질 게이트. 변경된 영역의 테스트·린트가 실패하면 에이전트가 작업을 끝내지 못하게 한다.

- 백엔드/테스트(.py) 변경 → BASE_URL이 필요 없는 pytest 전체 (fastapi-app/.venv 가 있으면 그 Python 사용)
- 프런트엔드 src 변경   → npm run lint (node_modules 가 있을 때만)
- 같은 세션에서 최대 MAX_BLOCKS 회까지만 막아 무한 루프를 방지한다.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from _hooklib import REPO_ROOT, emit, read_event

APP_DIR = REPO_ROOT / "fastapi-app"
FRONTEND_DIR = APP_DIR / "frontend"
MAX_BLOCKS = 3


def git_lines(*args: str) -> list[str]:
    try:
        out = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return []
    return out.stdout.splitlines() if out.returncode == 0 else []


def changed_files() -> set[str]:
    """작업 트리 변경 + (cloud agent처럼 이미 커밋한 경우) 기본 브랜치 대비 변경 파일."""
    files = {line[3:].strip().strip('"') for line in git_lines("status", "--porcelain", "-uall") if len(line) > 3}
    for base in ("origin/HEAD", "origin/main", "main"):
        merge_base = git_lines("merge-base", "HEAD", base)
        if merge_base:
            files.update(git_lines("diff", "--name-only", merge_base[0], "HEAD"))
            break
    return files


def project_python() -> str:
    for candidate in (APP_DIR / ".venv" / "bin" / "python", APP_DIR / ".venv" / "Scripts" / "python.exe"):
        if candidate.exists():
            return str(candidate)
    return sys.executable


def run(cmd: list[str], cwd: Path, timeout: int) -> tuple[bool, str]:
    try:
        out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"{' '.join(cmd)} 가 {timeout}초 안에 끝나지 않았습니다."
    except OSError as error:
        return True, f"(건너뜀: {error})"
    return out.returncode == 0, (out.stdout + out.stderr)[-2500:]


def block_count(session: str, increment: bool) -> int:
    state = Path(tempfile.gettempdir()) / f"fastapi-todos-quality-gate-{session or 'default'}.json"
    count = 0
    if state.exists():
        try:
            count = json.loads(state.read_text())["blocks"]
        except (ValueError, KeyError, OSError):
            count = 0
    if increment:
        count += 1
        state.write_text(json.dumps({"blocks": count}))
    return count


def main() -> None:
    event = read_event()
    session = str(event.get("sessionId") or event.get("session_id") or "")
    files = changed_files()
    failures, notes = [], []

    if any(f.startswith("fastapi-app/") and f.endswith(".py") and "/frontend/" not in f for f in files):
        python = project_python()
        has_deps = subprocess.run([python, "-c", "import fastapi, pytest, sqlalchemy"],
                                  capture_output=True).returncode == 0
        if has_deps:
            ok, log = run([python, "-m", "pytest", "tests", "-q", "-x",
                           "--ignore=tests/test_ui.py", "--ignore=tests/test_deployed.py"],
                          APP_DIR, timeout=150)
            if not ok:
                failures.append("백엔드 테스트 실패:\n" + log)
        else:
            notes.append("Python 의존성이 없어 pytest 게이트를 건너뛰었습니다.")

    if any(f.startswith("fastapi-app/frontend/src/") for f in files):
        npm = shutil.which("npm")
        if npm and (FRONTEND_DIR / "node_modules").exists():
            ok, log = run([npm, "run", "lint", "--silent"], FRONTEND_DIR, timeout=90)
            if not ok:
                failures.append("프런트엔드 lint 실패:\n" + log)
        else:
            notes.append("node_modules 가 없어 lint 게이트를 건너뛰었습니다.")

    if failures and block_count(session, increment=False) < MAX_BLOCKS:
        block_count(session, increment=True)
        reason = ("품질 게이트를 통과하지 못했습니다. 아래 실패를 고친 뒤 다시 검증하고 작업을 마치세요. "
                  "테스트를 삭제·skip 하거나 assert를 완화하지 마세요.\n\n" + "\n\n".join(failures))
        emit({
            "decision": "block",
            "reason": reason,
            "hookSpecificOutput": {"hookEventName": "Stop", "decision": "block", "reason": reason},
        })
        return

    if failures:
        notes.append(f"품질 게이트가 {MAX_BLOCKS}회 차단 후에도 실패해 사람의 검토가 필요합니다.")
    message = " / ".join(notes)
    emit({"systemMessage": message} if message else {})


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    main()
