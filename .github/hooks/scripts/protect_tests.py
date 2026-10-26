"""Refactorer 전용(agent-scoped) preToolUse: 테스트 파일 수정을 차단한다.

리팩토링은 동작을 보존해야 하므로 '테스트를 고쳐서 통과시키는' 우회를 막는다.
"""
import re

from _hooklib import (EDIT_TOOLS, SHELL_TOOLS, allow_silently, command_text, deny,
                      path_values, read_event, tool_name)

TEST_PATH = re.compile(r"(^|/)(fastapi-app/)?tests/[^/]*\.py$")
SHELL_WRITE = re.compile(r"(>|\btee\b|\bsed\s+-i|\bmv\b|\brm\b|\bcp\b|\bgit\s+(checkout|restore)\b).*\btests/")


def main() -> None:
    event = read_event()
    name = tool_name(event)

    if name in EDIT_TOOLS and any(TEST_PATH.search(path) for path in path_values(event)):
        deny("Refactorer는 테스트 파일을 수정할 수 없습니다. 테스트가 깨진다면 리팩토링이 동작을 바꾼 것이니 변경을 되돌리세요.")
    if name in SHELL_TOOLS and SHELL_WRITE.search(command_text(event)):
        deny("Refactorer는 셸 명령으로도 테스트 파일을 변경할 수 없습니다.")
    allow_silently()


if __name__ == "__main__":
    main()
