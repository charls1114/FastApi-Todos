# 릴리즈 양식

새 버전을 릴리즈할 때 아래 순서와 본문 양식을 따른다. (기준: v4.0.0, v5.0.0)

## 릴리즈 순서

1. 작업 브랜치를 PR로 `main`에 병합한다.
2. `main`을 최신으로 맞추고 병합 커밋에 태그를 붙인다.
   ```bash
   git checkout main && git pull
   git tag vX.Y.Z
   git push origin refs/tags/vX.Y.Z   # 같은 이름의 브랜치가 있어도 태그만 올라가도록 refs/tags/ 를 붙인다
   ```
3. 화면 캡처를 1920x940 크기로 준비한다. 파일 이름은 `vX.Y.Z-board.png`, `vX.Y.Z-calendar.png`.
4. 아래 본문 양식을 채워 파일(예: `release-vX.Y.Z.md`)로 저장한 뒤 릴리즈를 만든다.
   ```bash
   gh release create vX.Y.Z --verify-tag --title vX.Y.Z --latest \
     --notes-file release-vX.Y.Z.md vX.Y.Z-board.png vX.Y.Z-calendar.png
   ```
   함께 올린 캡처 파일은 `https://github.com/charls1114/FastApi-Todos/releases/download/vX.Y.Z/<파일 이름>` 주소로 본문에 표시된다.
5. 변경 사항은 `git log --no-merges vA.B.C..main` 으로 이전 릴리즈 이후 커밋을 확인해 정리한다.

## 본문 양식

```markdown
## vX.Y.Z

### 기능 추가
- 사용자가 새로 할 수 있게 된 일

### 결함 수정
- 잘못 동작하던 내용과 고친 결과

### 변경 내역
- 동작·구조·설정·배포·테스트 등 기능 추가나 결함 수정이 아닌 변경

### 화면 캡처
#### 칸반 보드
<img width="1920" height="940" alt="vX.Y.Z 칸반 보드" src="https://github.com/charls1114/FastApi-Todos/releases/download/vX.Y.Z/vX.Y.Z-board.png" />

#### 달력 보기
<img width="1920" height="940" alt="vX.Y.Z 달력 보기" src="https://github.com/charls1114/FastApi-Todos/releases/download/vX.Y.Z/vX.Y.Z-calendar.png" />
```

- 항목은 "~추가", "~수정", "~변경"처럼 명사형으로 끝낸다.
- 해당하는 내용이 없는 섹션은 지운다.
