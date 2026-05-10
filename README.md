# Weekly AI/Dev Brief

지난 7일 동안의 AI, 개발 이슈, 흥미로운 개발 도구 소식을 모아 매주 일요일 09:00 KST에 GitHub Pages 정적 사이트로 배포하는 개인용 자동화입니다.

수집은 공개 RSS, Hacker News Algolia API, 지정한 GitHub 저장소 릴리스에서 합니다. `GEMINI_API_KEY`가 있으면 수집 근거만 사용해 한국어 요약을 만들고, 없으면 링크 중심의 기본 브리프를 생성합니다.

## 동작 방식

1. GitHub Actions가 매주 일요일 09:00 KST에 실행됩니다.
2. `build_pages.py`가 최신 브리프를 생성해 `public/briefs/YYYY-MM-DD.html`에 저장합니다.
3. `public/briefs/`에는 최근 4개 HTML만 남깁니다.
4. `public/index.html`은 최근 4개 목록을 포함한 정적 페이지로 갱신됩니다.
5. GitHub Pages가 `public/` 폴더를 배포합니다.

페이지 새로고침은 정적 HTML만 읽습니다. 새 수집과 Gemini 호출은 GitHub Actions 실행 시점에만 일어납니다.

## 로컬 실행

브리프 파일만 생성:

```powershell
python weekly_brief.py
```

GitHub Pages용 정적 사이트까지 생성:

```powershell
python build_pages.py --keep 4
```

## 내가 해야 할 일

1. 이 폴더를 GitHub 저장소로 push합니다.
2. GitHub 저장소의 `Settings > Secrets and variables > Actions > Secrets`에 `GEMINI_API_KEY`를 추가합니다.
3. 같은 화면의 `Variables`에 `GEMINI_MODEL`을 추가하고 값은 `gemini-2.5-flash-lite`로 둡니다. 생략해도 기본값으로 동작합니다.
4. 저장소 `Settings > Pages`로 이동합니다.
5. `Build and deployment`의 Source를 `GitHub Actions`로 설정합니다.
6. `Actions` 탭에서 `Build Weekly Brief Pages` workflow를 수동 실행합니다.
7. 실행이 끝나면 `Settings > Pages`에 표시되는 URL로 접속합니다.

## 선택 설정

Actions Variables로 조정할 수 있습니다.

- `HN_QUERIES`: Hacker News 검색어 CSV
- `FEED_URLS`: RSS/Atom URL CSV
- `GITHUB_REPOS`: 릴리스를 볼 GitHub 저장소 CSV

Actions Secrets로 추가할 수 있습니다.

- `GITHUB_TOKEN`: 저장소 기본 토큰이 자동 제공됩니다. 외부 저장소 rate limit 때문에 별도 토큰이 필요할 때만 추가하세요.
- `OPENAI_API_KEY`: Gemini를 쓰지 않을 때 fallback 요약용입니다.

## 수집 범위 바꾸기

기본값은 AI 제품/모델, 개발자 도구, SDK/프레임워크 릴리스 쪽으로 맞춰져 있습니다.

예시:

```text
HN_QUERIES=AI agent,MCP,Codex,Claude Code,Cursor,TypeScript,Next.js
GITHUB_REPOS=openai/codex,microsoft/vscode,vercel/next.js,modelcontextprotocol/typescript-sdk
```
