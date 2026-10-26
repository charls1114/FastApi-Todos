"""Copilot Hook 스크립트 공용 유틸리티.

Copilot 하네스·Copilot cloud agent(camelCase: toolName/toolArgs)와
VS Code Local 하네스(snake_case: tool_name/tool_input) 입력을 모두 처리한다.
출력도 두 형식을 함께 내보내 어느 런타임에서든 같은 결정을 내리게 한다.
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def read_event() -> dict:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def tool_name(event: dict) -> str:
    return str(event.get("toolName") or event.get("tool_name") or "")


def tool_args(event: dict):
    args = event.get("toolArgs", event.get("tool_input"))
    if isinstance(args, str):
        try:
            return json.loads(args)
        except json.JSONDecodeError:
            return args
    return args if args is not None else {}


def args_text(event: dict) -> str:
    """인수 전체를 하나의 문자열로 만들어 패턴 검사에 사용한다."""
    args = tool_args(event)
    text = args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)
    return text.replace("\\\\", "/").replace("\\", "/")


def path_values(event: dict) -> list[str]:
    """인수 중 파일 경로로 보이는 값(path, filePath, file_path, paths ...)만 모은다."""
    found: list[str] = []

    def walk(node, key=""):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, k)
        elif isinstance(node, list):
            for item in node:
                walk(item, key)
        elif isinstance(node, str) and ("path" in key.lower() or "file" in key.lower()):
            found.append(node.replace("\\", "/"))

    walk(tool_args(event))
    return found


def command_text(event: dict) -> str:
    """셸 도구의 명령 문자열."""
    args = tool_args(event)
    if isinstance(args, dict):
        return str(args.get("command") or args.get("cmd") or args.get("script") or "")
    return str(args)


def emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False))
    sys.stdout.flush()


def deny(reason: str) -> None:
    """preToolUse 거부. Copilot 형식 + VS Code(Local) 형식 + exit 2를 모두 사용한다."""
    emit({
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        },
    })
    sys.stderr.write(reason + "\n")
    sys.exit(2)


def allow_silently() -> None:
    """결정하지 않음: 일반 권한 흐름으로 넘긴다."""
    emit({})
    sys.exit(0)


EDIT_TOOLS = {
    # Copilot 런타임(CLI·cloud agent)
    "edit", "create", "str_replace_editor", "apply_patch",
    # Claude 호환 이름
    "Edit", "Write", "MultiEdit",
    # VS Code Local 하네스
    "editFiles", "create_file", "replace_string_in_file",
    "multi_replace_string_in_file", "insert_edit_into_file", "apply_patch",
}

SHELL_TOOLS = {"bash", "powershell", "Bash", "run_in_terminal", "runInTerminal", "execute"}
