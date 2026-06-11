from dataclasses import dataclass

from app.models import MarketSnapshot


US_VOLUME_RATIO_MIN = 2.0
US_VOLUME_RATIO_MAX = 20.0
US_CHANGE_PCT_MIN = 2.0
US_CHANGE_PCT_MAX = 12.0
US_MIN_TRADING_VALUE_KRW = 500_000_000
US_MIN_PRICE = 2.0
EXCLUDED_US_SYMBOLS = {
    "AMDY",
    "CONY",
    "ARKF",
    "ARKG",
    "ARKK",
    "ARKQ",
    "ARKW",
    "ARKX",
    "DRIP",
    "FNGD",
    "FNGU",
    "GDXD",
    "LABD",
    "LABU",
    "MSOS",
    "MSTY",
    "PLTY",
    "SARK",
    "SDOW",
    "SDS",
    "SOXL",
    "SOXS",
    "SPXL",
    "SPXS",
    "SPXU",
    "TECL",
    "TECS",
    "TQQQ",
    "SQQQ",
    "TNA",
    "TZA",
    "TSLL",
    "TSLS",
    "NVDL",
    "NVD",
    "NVDQ",
    "NVDY",
    "UVXY",
    "VXX",
    "KORU",
    "YINN",
    "YANG",
    "GGN",
    "YMAX",
    "YMAG",
    "ULTY",
}
EXCLUDED_US_PRODUCT_KEYWORDS = {
    " ETF",
    " ETN",
    "EXCHANGE TRADED",
    "OPTION INCOME",
    "INCOME STRATEGY",
    "COVERED CALL",
    "BUYWRITE",
    "PREMIUM INCOME",
    "LEVERAGED",
    "INVERSE",
    "ULTRAPRO",
    "2X",
    "3X",
    "YIELDMAX",
}


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

    _append_intraday_strength(snapshot, reasons, risks, block_vwap=False)

    return FilterDecision(passed=not risks, reasons=reasons, risks=risks)


def _evaluate_us(snapshot: MarketSnapshot) -> FilterDecision:
    reasons: list[str] = []
    risks: list[str] = []
    blocking_risks: list[str] = []

    if _is_excluded_us_product(snapshot):
        blocking_risks.append("레버리지/인버스/파생형 ETF 제외")

    if snapshot.price <= 0:
        blocking_risks.append("현재가 0 이하")
    elif snapshot.price < US_MIN_PRICE:
        blocking_risks.append("2달러 미만 저가주 제외")

    if US_VOLUME_RATIO_MIN <= snapshot.volume_ratio <= US_VOLUME_RATIO_MAX:
        reasons.append("거래량 증가율 200%~2000% 구간")
    elif snapshot.volume_ratio > US_VOLUME_RATIO_MAX:
        blocking_risks.append("거래량 증가율 2000% 초과")
    else:
        blocking_risks.append("거래량 증가율 200% 미만")

    if snapshot.trading_value_krw >= 30_000_000_000:
        reasons.append("미장 거래대금 300억 이상")
    elif snapshot.trading_value_krw >= 5_000_000_000:
        reasons.append("미장 거래대금 50억 이상")
    elif snapshot.trading_value_krw >= US_MIN_TRADING_VALUE_KRW:
        reasons.append("미장 최소 유동성 통과")
    else:
        blocking_risks.append("미장 거래대금 5억 미만")

    if 3 <= snapshot.change_pct <= 8:
        reasons.append("상승률이 급등 초입 핵심 구간")
    elif US_CHANGE_PCT_MIN <= snapshot.change_pct < 3:
        reasons.append("초기 상승 모멘텀")
    elif 8 < snapshot.change_pct <= US_CHANGE_PCT_MAX:
        reasons.append("강한 초입 모멘텀")
        risks.append("이미 일부 오른 구간이라 추격 주의")
    elif snapshot.change_pct > US_CHANGE_PCT_MAX:
        blocking_risks.append("12% 초과 상승은 급등 초입 제외")
    else:
        blocking_risks.append("등락률 2% 미만")

    _append_intraday_strength(snapshot, reasons, blocking_risks, block_vwap=True)
    risks.extend(blocking_risks)

    return FilterDecision(passed=not blocking_risks, reasons=reasons, risks=risks)


def _is_excluded_us_product(snapshot: MarketSnapshot) -> bool:
    symbol = snapshot.symbol.strip().upper()
    if symbol in EXCLUDED_US_SYMBOLS:
        return True

    name = f" {snapshot.name.strip().upper()} "
    return any(keyword in name for keyword in EXCLUDED_US_PRODUCT_KEYWORDS)


def _append_intraday_strength(
    snapshot: MarketSnapshot,
    reasons: list[str],
    risks: list[str],
    block_vwap: bool,
) -> None:
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
            risks.append("VWAP 아래로 이탈" if block_vwap else "VWAP 아래로 이탈 주의")
