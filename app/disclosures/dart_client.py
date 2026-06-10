from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

KST = timezone(timedelta(hours=9))
DART_LIST_URL = "https://opendart.fss.or.kr/api/list.json"

HIGH_RISK_KEYWORDS = (
    "유상증자",
    "감자",
    "전환사채",
    "신주인수권부사채",
    "교환사채",
    "관리종목",
    "거래정지",
    "상장폐지",
    "불성실공시",
    "횡령",
    "배임",
    "회생절차",
    "파산",
    "감사의견",
    "정정제출요구",
)

MEDIUM_RISK_KEYWORDS = (
    "주요사항보고서",
    "최대주주 변경",
    "최대주주의 변경",
    "담보제공",
    "타법인주식",
    "자기주식처분",
    "소송",
)

IGNORE_KEYWORDS = (
    "임원ㆍ주요주주특정증권등소유상황보고서",
    "임원·주요주주특정증권등소유상황보고서",
    "최대주주등소유주식변동신고서",
    "대규모기업집단현황공시",
    "기업지배구조보고서공시",
    "분기보고서",
    "반기보고서",
    "사업보고서",
)


class DartClient:
    def __init__(self, api_key: str | None, http_client: httpx.Client | None = None) -> None:
        self.api_key = api_key
        self.http_client = http_client or httpx.Client(timeout=10)

    def recent_disclosures(self, stock_code: str, days: int = 7, page_count: int = 20) -> list[dict[str, Any]]:
        if not self.api_key:
            return []

        end = datetime.now(KST).date()
        begin = end - timedelta(days=days)
        response = self.http_client.get(
            DART_LIST_URL,
            params={
                "crtfc_key": self.api_key,
                "stock_code": stock_code,
                "bgn_de": begin.strftime("%Y%m%d"),
                "end_de": end.strftime("%Y%m%d"),
                "sort": "date",
                "sort_mth": "desc",
                "page_no": "1",
                "page_count": str(page_count),
            },
        )
        response.raise_for_status()
        payload = response.json()
        status = str(payload.get("status"))
        if status == "013":
            return []
        if status != "000":
            raise RuntimeError(f"DART disclosure request failed: {payload.get('message') or payload}")
        items = payload.get("list") or []
        return [item for item in items if isinstance(item, dict)]

    def risk_score(self, stock_code: str, days: int = 7) -> float:
        disclosures = self.recent_disclosures(stock_code, days=days)
        return evaluate_disclosure_risk(disclosures)


def evaluate_disclosure_risk(disclosures: list[dict[str, Any]]) -> float:
    risk = 0.0
    for disclosure in disclosures:
        title = str(disclosure.get("report_nm") or "")
        if _should_ignore(title):
            continue
        if any(keyword in title for keyword in HIGH_RISK_KEYWORDS):
            risk += 10.0
        elif any(keyword in title for keyword in MEDIUM_RISK_KEYWORDS):
            risk += 4.0
    return min(10.0, risk)


def _should_ignore(title: str) -> bool:
    normalized = title.replace(" ", "")
    return any(keyword.replace(" ", "") in normalized for keyword in IGNORE_KEYWORDS)
