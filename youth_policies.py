"""Find potentially relevant OnTong Youth policies and notify on new matches."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

API_URL = "https://www.youthcenter.go.kr/go/ythip/getPlcy"
DETAIL_URL = "https://www.youthcenter.go.kr/youthPolicy/ythPlcyTotalSearch/ythPlcyDetail/"
TECH = re.compile(r"(?i)(?<![a-z])(?:AI|IT|SW|LLM|ICT)(?![a-z])|인공지능|개발|코딩|프로그래밍|데이터|소프트웨어|정보기술|컴퓨터|클라우드|보안|디지털")
HOUSING = re.compile(r"주거|주택|임대|전월세|월세|전세|매매|보증금|기숙사")


def age_on(birth: str, today: dt.date) -> int:
    born = dt.date.fromisoformat(birth)
    if born > today:
        raise ValueError("Birth date is in the future")
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def get_page(api_key: str, page: int, *, category: str = "") -> tuple[list[dict], int]:
    params = {"apiKeyNm": api_key, "pageNum": page, "pageSize": 50, "pageType": 1, "rtnType": "json"}
    if category:
        params["lclsfNm"] = category
    url = API_URL + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": "daily-ai-dev-brief/1.0"})
    with urllib.request.urlopen(request, timeout=25) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if str(payload.get("resultCode")) != "200":
        raise ValueError("OnTong Youth API returned an unsuccessful result")
    result = payload.get("result") or {}
    records = result.get("youthPolicyList") or []
    total = int((result.get("pagging") or {}).get("totCount") or 0)
    return [row for row in records if isinstance(row, dict)], total


def collect(api_key: str) -> list[dict]:
    records: dict[str, dict] = {}
    # Recent policies plus a focused housing query. The search remains bounded.
    for category, pages in (("", 4), ("주거", 3)):
        for page in range(1, pages + 1):
            rows, total = get_page(api_key, page, category=category)
            for row in rows:
                number = str(row.get("plcyNo") or "")
                if number:
                    records[number] = row
            if not rows or (total and page * len(rows) >= total):
                break
    return list(records.values())


def application_end(value: str) -> dt.date | None:
    dates = re.findall(r"\b(?:20\d{2})[./-]?\d{1,2}[./-]?\d{1,2}\b", re.sub(r"\s+", "", value))
    for raw in reversed(dates):
        digits = re.sub(r"\D", "", raw)
        try:
            return dt.date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
        except ValueError:
            continue
    return None


def candidate(row: dict, age: int, today: dt.date) -> dict | None:
    title = str(row.get("plcyNm") or "").strip()
    number = str(row.get("plcyNo") or "")
    if not title or not number or row.get("plcyAprvSttsCd") not in (None, "", "0044002"):
        return None
    topic = " ".join(str(row.get(key) or "")[:400] for key in
                     ("plcyNm", "plcyKywdNm", "lclsfNm", "mclsfNm"))
    kind = "주거" if HOUSING.search(topic) else "AI·IT·개발" if TECH.search(topic) else ""
    if not kind:
        return None
    region = str(row.get("zipCd") or "").strip()
    region_codes = re.findall(r"(?<!\d)\d{2,5}(?!\d)", region)
    if region and "전국" not in region and not any(code.startswith("11") or code in {"0", "00", "00000"} for code in region_codes):
        return None
    try:
        min_age = int(row.get("sprtTrgtMinAge") or 0)
        max_age = int(row.get("sprtTrgtMaxAge") or 200)
    except (ValueError, TypeError):
        return None
    if not min_age <= age <= max_age:
        return None
    school = str(row.get("schoolCd") or "")
    if school and school not in {"0049005", "0049010"}:
        return None
    period = str(row.get("aplyYmd") or "").strip()
    period_code = str(row.get("aplyPrdSeCd") or "")
    if period_code == "0057003" or "마감" in period:
        return None
    end = application_end(period)
    if end and end < today:
        return None
    dates = re.findall(r"\b(?:20\d{2})[./-]?\d{1,2}[./-]?\d{1,2}\b", re.sub(r"\s+", "", period))
    if len(dates) >= 2:
        try:
            first = re.sub(r"\D", "", dates[0])
            start = dt.date(int(first[:4]), int(first[4:6]), int(first[6:8]))
            if start > today:
                return None
        except ValueError:
            pass
    if not end and period_code != "0057002" and "상시" not in period:
        return None
    raw_url = str(row.get("aplyUrlAddr") or row.get("refUrlAddr1") or row.get("refUrlAddr2") or "").strip()
    parsed_url = urllib.parse.urlsplit(raw_url)
    link = raw_url if parsed_url.scheme == "https" and parsed_url.netloc else DETAIL_URL + urllib.parse.quote(number)
    checks = []
    if not region:
        checks.append("지역")
    if str(row.get("jobCd") or "") not in {"", "0013010"}:
        checks.append("취업 상태")
    if str(row.get("sbizCd") or "") not in {"", "0014010"}:
        checks.append("특화 자격")
    if str(row.get("earnCndSeCd") or "") not in {"", "0043001"}:
        checks.append("소득")
    if str(row.get("addAplyQlfcCndCn") or "").strip():
        checks.append("추가 자격")
    return {"id": number, "title": title[:90], "kind": kind, "url": link,
            "period": period[:60] or "상시", "checks": checks,
            "summary": " ".join(str(row.get("plcySprtCn") or row.get("plcyExplnCn") or "").split())[:110]}


def find_candidates(api_key: str, birth: str, today: dt.date) -> list[dict]:
    age = age_on(birth, today)
    found = [match for row in collect(api_key) if (match := candidate(row, age, today))]
    return sorted(found, key=lambda item: (item["kind"] != "주거", item["title"]))[:20]


def markdown(candidates: list[dict]) -> str:
    if not candidates:
        return ""
    lines = ["", "## 나에게 맞을 수 있는 청년정책", "", "서울 거주·재학·연령과 관심 분야를 기준으로 추린 후보입니다. 신청 전 원문의 세부 자격을 확인하세요.", ""]
    for item in candidates[:8]:
        check = f" 추가 확인: {', '.join(item['checks'])}." if item["checks"] else ""
        title = re.sub(r"[\[\]()]", "", item["title"])
        lines.append(f"- [{title}]({item['url']}) — {item['kind']} · 접수: {item['period']}.{check}")
    return "\n".join(lines) + "\n"


def new_matches(candidates: list[dict], state_path: Path) -> tuple[list[dict], set[str]]:
    current = {item["id"] for item in candidates}
    if not state_path.exists():
        return [], current  # First run sets a baseline instead of sending a backlog.
    try:
        previous = set(json.loads(state_path.read_text(encoding="utf-8")).get("seen", []))
    except (ValueError, OSError):
        return [], current
    return [item for item in candidates if item["id"] not in previous], previous | current


def save_seen(state_path: Path, ids: set[str]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"seen": sorted(ids)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def notify_telegram(candidates: list[dict]) -> bool:
    if not candidates:
        return True
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("Youth policy notifications skipped: Telegram secrets unavailable")
        return False
    lines = ["새로 확인된 청년정책 후보", ""]
    for item in candidates[:5]:
        checks = f" · 확인: {', '.join(item['checks'])}" if item["checks"] else ""
        lines.extend([f"• {item['title']} ({item['kind']})", f"  접수: {item['period']}{checks}", f"  {item['url']}", ""])
    body = json.dumps({"chat_id": chat_id, "text": "\n".join(lines)[:4000], "disable_web_page_preview": True}).encode("utf-8")
    request = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=body,
                                     headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return bool(json.loads(response.read().decode("utf-8")).get("ok"))
    except (OSError, ValueError):
        print("Youth policy notification failed")
        return False


def today_seoul() -> dt.date:
    return dt.datetime.now(ZoneInfo("Asia/Seoul")).date()
