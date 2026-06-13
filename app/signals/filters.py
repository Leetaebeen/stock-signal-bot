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
    "EEMA",
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
    "ISHARES",
    "SPDR",
    "NUVEEN",
    "PACER",
    "FT VEST",
    "OPTION INCOME",
    "INCOME STRATEGY",
    "COVERED CALL",
    "BUYWRITE",
    "DYNAMIC OVERWRITE",
    "PREMIUM INCOME",
    "TARGET INCOME",
    "PREFERRED",
    "PREF",
    "COHEN & STEERS",
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


@dataclass(frozen=True)
class FilterConfig:
    us_volume_ratio_min: float = US_VOLUME_RATIO_MIN
    us_volume_ratio_max: float = US_VOLUME_RATIO_MAX
    us_change_pct_min: float = US_CHANGE_PCT_MIN
    us_change_pct_max: float = US_CHANGE_PCT_MAX
    us_min_trading_value_krw: float = US_MIN_TRADING_VALUE_KRW
    us_min_price: float = US_MIN_PRICE


def filter_config_from_settings(settings) -> FilterConfig:
    return FilterConfig(
        us_volume_ratio_min=float(settings.us_filter_volume_ratio_min),
        us_volume_ratio_max=float(settings.us_filter_volume_ratio_max),
        us_change_pct_min=float(settings.us_filter_change_pct_min),
        us_change_pct_max=float(settings.us_filter_change_pct_max),
        us_min_trading_value_krw=float(settings.us_filter_min_trading_value_krw),
        us_min_price=float(settings.us_filter_min_price),
    )


def evaluate_candidate_filter(snapshot: MarketSnapshot, config: FilterConfig | None = None) -> FilterDecision:
    if snapshot.market != "US":
        return FilterDecision(passed=False, reasons=[], risks=["미국장만 지원"])
    return _evaluate_us(snapshot, config or FilterConfig())


def filter_candidates(
    snapshots: list[MarketSnapshot],
    config: FilterConfig | None = None,
) -> list[MarketSnapshot]:
    config = config or FilterConfig()
    return [snapshot for snapshot in snapshots if evaluate_candidate_filter(snapshot, config).passed]


def _evaluate_us(snapshot: MarketSnapshot, config: FilterConfig) -> FilterDecision:
    reasons: list[str] = []
    risks: list[str] = []
    blocking_risks: list[str] = []
    explosion_candidate = _is_us_explosion_candidate(snapshot)

    if is_excluded_us_product(snapshot):
        blocking_risks.append("ETF/레버리지/파생형 상품 제외")

    if snapshot.price <= 0:
        blocking_risks.append("현재가 0 이하")
    elif snapshot.price < config.us_min_price and not explosion_candidate:
        blocking_risks.append("2달러 미만 저가주 제외")

    if explosion_candidate:
        reasons.append("초급등 모드: 12% 이상 급등과 거래량 90% 이상 증가")
        if snapshot.price < config.us_min_price:
            risks.append("저가주라 스프레드와 거래정지 위험 주의")
        if snapshot.change_pct > 80:
            risks.append("이미 크게 오른 구간이라 추격매수 위험 높음")
        _append_intraday_strength(snapshot, reasons, risks, block_vwap=False)
        risks.extend(blocking_risks)
        return FilterDecision(passed=not blocking_risks, reasons=reasons, risks=risks)

    if config.us_volume_ratio_min <= snapshot.volume_ratio <= config.us_volume_ratio_max:
        reasons.append("거래량 증가율 200%~2000% 구간")
    elif snapshot.volume_ratio > config.us_volume_ratio_max:
        blocking_risks.append("거래량 증가율 2000% 초과")
    else:
        blocking_risks.append("거래량 증가율 200% 미만")

    if snapshot.trading_value_krw >= 30_000_000_000:
        reasons.append("미장 거래대금 300억 이상")
    elif snapshot.trading_value_krw >= 5_000_000_000:
        reasons.append("미장 거래대금 50억 이상")
    elif snapshot.trading_value_krw >= config.us_min_trading_value_krw:
        reasons.append("미장 최소 유동성 통과")
    else:
        blocking_risks.append("미장 거래대금 5억 미만")

    if 3 <= snapshot.change_pct <= 8:
        reasons.append("상승률이 급등 초입 구간")
    elif config.us_change_pct_min <= snapshot.change_pct < 3:
        reasons.append("초기 상승 모멘텀")
    elif 8 < snapshot.change_pct <= config.us_change_pct_max:
        reasons.append("강한 상승 모멘텀")
        risks.append("이미 빠르게 오른 구간이라 추격 주의")
    elif snapshot.change_pct > config.us_change_pct_max:
        blocking_risks.append("12% 초과 상승은 일반 초입 필터 제외")
    else:
        blocking_risks.append("등락률 2% 미만")

    _append_intraday_strength(snapshot, reasons, blocking_risks, block_vwap=True)
    risks.extend(blocking_risks)

    return FilterDecision(passed=not blocking_risks, reasons=reasons, risks=risks)


def _is_us_explosion_candidate(snapshot: MarketSnapshot) -> bool:
    return (
        12 < snapshot.change_pct <= 300
        and snapshot.volume_ratio >= 1.9
        and snapshot.trading_value_krw >= 100_000_000
        and snapshot.price >= 0.1
    )


def is_excluded_us_product(snapshot: MarketSnapshot) -> bool:
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
            risks.append("고가 대비 이탈폭 큼")

    if snapshot.vwap_price and snapshot.vwap_price > 0:
        if snapshot.price >= snapshot.vwap_price:
            reasons.append("VWAP 위에서 유지")
        else:
            risks.append("VWAP 아래로 이탈" if block_vwap else "VWAP 아래로 이탈 주의")
