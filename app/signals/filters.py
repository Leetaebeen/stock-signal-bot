from dataclasses import dataclass

from app.models import MarketSnapshot


@dataclass(frozen=True)
class FilterDecision:
    passed: bool
    reasons: list[str]
    risks: list[str]


def evaluate_candidate_filter(snapshot: MarketSnapshot) -> FilterDecision:
    if snapshot.market == "KR":
        return _evaluate_kr(snapshot)
    return _evaluate_us(snapshot)


def filter_candidates(snapshots: list[MarketSnapshot]) -> list[MarketSnapshot]:
    return [snapshot for snapshot in snapshots if evaluate_candidate_filter(snapshot).passed]


def _evaluate_kr(snapshot: MarketSnapshot) -> FilterDecision:
    reasons: list[str] = []
    risks: list[str] = []

    if snapshot.price < 1_000:
        risks.append("현재가 1,000원 미만")

    if snapshot.trading_value_krw >= 30_000_000_000:
        reasons.append("거래대금 300억 이상")
    else:
        risks.append("거래대금 300억 미만")

    if 2 <= snapshot.change_pct <= 15:
        reasons.append("등락률이 단기 후보 구간")
    elif snapshot.change_pct > 18:
        risks.append("이미 과열된 상승률")
    else:
        risks.append("등락률 조건 미충족")

    _append_intraday_strength(snapshot, reasons, risks)

    return FilterDecision(passed=not risks, reasons=reasons, risks=risks)


def _evaluate_us(snapshot: MarketSnapshot) -> FilterDecision:
    reasons: list[str] = []
    risks: list[str] = []
    blocking_risks: list[str] = []

    if snapshot.price < 1:
        blocking_risks.append("1달러 미만 저가주 제외")
    elif snapshot.price < 2:
        risks.append("2달러 미만 저가주는 변동성 큼")

    if snapshot.trading_value_krw >= 30_000_000_000:
        reasons.append("미장 거래대금 300억 이상")
    elif snapshot.trading_value_krw >= 5_000_000_000:
        reasons.append("미장 거래대금 50억 이상")
    elif snapshot.trading_value_krw >= 500_000_000:
        reasons.append("미장 최소 유동성 통과")
    else:
        blocking_risks.append("미장 거래대금 5억 미만")

    if 3 <= snapshot.change_pct <= 12:
        reasons.append("상승률이 단기 모멘텀 구간")
    elif 1.5 <= snapshot.change_pct < 3:
        reasons.append("초기 상승 모멘텀")
    elif 12 < snapshot.change_pct <= 25:
        reasons.append("강한 급등 모멘텀")
        risks.append("이미 크게 오른 구간이라 추격 주의")
    elif snapshot.change_pct > 25:
        blocking_risks.append("25% 초과 급등주는 추격 제외")
    else:
        blocking_risks.append("등락률 조건 미충족")

    _append_intraday_strength(snapshot, reasons, risks)
    risks.extend(blocking_risks)

    return FilterDecision(passed=not blocking_risks, reasons=reasons, risks=risks)


def _append_intraday_strength(snapshot: MarketSnapshot, reasons: list[str], risks: list[str]) -> None:
    if snapshot.high_price and snapshot.high_price > 0:
        high_pullback_pct = ((snapshot.high_price - snapshot.price) / snapshot.high_price) * 100
        if high_pullback_pct <= 3:
            reasons.append("고가 대비 3% 이내 유지")
        else:
            risks.append("고가 대비 이탈폭이 큼")

    if snapshot.vwap_price and snapshot.vwap_price > 0:
        if snapshot.price >= snapshot.vwap_price:
            reasons.append("VWAP 위에서 유지")
        else:
            risks.append("VWAP 아래로 이탈")
