# Weekly AI/Dev Brief

지난 7일 동안의 AI, 개발 이슈, 흥미로운 개발 도구 소식을 모아 최신 HTML 브리프로 보여주는 개인용 Vercel 앱입니다.

수집은 공개 RSS, Hacker News Algolia API, 지정한 GitHub 저장소 릴리스에서 합니다. `GEMINI_API_KEY`가 있으면 수집 근거만 사용해 한국어 요약을 만들고, 없으면 링크 중심의 기본 브리프를 생성합니다.

## 로컬 실행

```powershell
python weekly_brief.py
```

생성 결과는 `out/weekly-ai-dev-brief-YYYY-MM-DD.html`과 `.md`로 저장됩니다.

## Vercel 배포

1. 이 폴더를 GitHub 저장소로 올립니다.
2. Vercel에서 새 프로젝트로 import 합니다.
3. Vercel 환경 변수에 아래 값을 넣습니다.
4. 배포하면 루트 페이지(`/`)에서 최신 브리프를 바로 볼 수 있습니다.
5. `vercel.json`의 Cron은 `/api/cron`을 매주 일요일 00:00 UTC, 즉 09:00 KST에 호출합니다.

이 버전은 이전 브리프를 저장하지 않습니다. 페이지를 열 때마다 새로 수집한 최신 브리프만 보여줍니다.

## 입력해야 할 값

필수에 가까운 값:

- `GEMINI_API_KEY`: 한국어 요약 생성용입니다. 없으면 기본 링크 브리프만 생성됩니다.

보안용 선택값:

- `CRON_SECRET`: 설정하면 Vercel Cron HTML 요청만 검사합니다. 루트 페이지의 JSON 호출은 공개 접근을 허용합니다.

선택 조정값:

- `GEMINI_MODEL`: 기본값 `gemini-2.5-flash-lite`
- `OPENAI_API_KEY`: Gemini를 쓰지 않을 때 fallback 요약용
- `OPENAI_MODEL`: OpenAI fallback 모델. 기본값 `gpt-4.1-mini`
- `GITHUB_TOKEN`: GitHub API rate limit 완화용
- `HN_QUERIES`: Hacker News 검색어 CSV
- `FEED_URLS`: RSS/Atom URL CSV
- `GITHUB_REPOS`: 릴리스를 볼 GitHub 저장소 CSV
- `BRIEF_TIMEZONE`: 기본값 `Asia/Seoul`
- `BRIEF_DAYS`: 기본값 `7`

## Vercel 구조

- `vercel.json`: 매주 일요일 09:00 KST 실행 스케줄
- `api/cron.py`: 최신 브리프 생성 후 HTML 또는 JSON으로 응답
- `public/index.html`: 최신 브리프를 보여주는 한 페이지 UI
- `weekly_brief.py`: 수집, 요약, HTML/Markdown 생성

## 수집 범위 바꾸기

기본값은 AI 제품/모델, 개발자 도구, SDK/프레임워크 릴리스 쪽으로 맞춰져 있습니다. 혼자 쓰는 브리프라면 `HN_QUERIES`, `FEED_URLS`, `GITHUB_REPOS`만 바꿔도 성격이 크게 달라집니다.

예시:

```text
HN_QUERIES=AI agent,MCP,Codex,Claude Code,Cursor,TypeScript,Next.js
GITHUB_REPOS=openai/codex,microsoft/vscode,vercel/next.js,modelcontextprotocol/typescript-sdk
```
