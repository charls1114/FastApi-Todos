"""preToolUse: 위험한 명령과 비밀 파일 접근을 차단하는 가드레일."""
import re

from _hooklib import SHELL_TOOLS, allow_silently, command_text, deny, path_values, read_event, tool_name

# 저장소 지침(.github/copilot-instructions.md)의 "보안·운영 금지 사항"을 결정적으로 강제한다.
SECRET_FILE = re.compile(r'(^|[/\s"\'=<>])\.env(?![\w.])')
DANGEROUS_COMMANDS = [
    (re.compile(r"docker(-|\s+)compose\b.*\bdown\b.*(\s-v\b|--volumes)"),
     "docker compose down -v 는 PostgreSQL 볼륨(할 일 데이터)을 삭제합니다."),
    (re.compile(r"docker\s+volume\s+(rm|prune)"), "Docker 볼륨 삭제 명령은 금지되어 있습니다."),
    (re.compile(r"git\s+push\b.*(--force\b|\s-f\b|--force-with-lease)"), "강제 푸시는 금지되어 있습니다."),
    (re.compile(r"git\s+reset\s+--hard"), "git reset --hard 는 작업 내용을 지웁니다. 되돌리기가 필요하면 사람에게 확인하세요."),
    (re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*\s+(/|~|\.|\*)(\s|$)"), "저장소·홈·루트 전체 삭제 명령은 금지되어 있습니다."),
    (re.compile(r"\bdrop\s+(database|schema\s+public)\b", re.IGNORECASE), "운영 DB/스키마 삭제는 금지되어 있습니다."),
]


def main() -> None:
    event = read_event()
    name = tool_name(event)

    if name in SHELL_TOOLS:
        command = command_text(event)
        if SECRET_FILE.search(command):
            deny(".env 파일은 비밀값을 담고 있어 에이전트가 읽거나 만들 수 없습니다. 예시 값은 .env.example을 사용하세요.")
        for pattern, reason in DANGEROUS_COMMANDS:
            if pattern.search(command):
                deny(f"차단된 명령: {reason}")
    elif any(SECRET_FILE.search(path) for path in path_values(event)):
        deny(".env 파일은 비밀값을 담고 있어 에이전트가 읽거나 수정할 수 없습니다. 예시 값은 .env.example을 사용하세요.")

    allow_silently()


if __name__ == "__main__":
    main()
