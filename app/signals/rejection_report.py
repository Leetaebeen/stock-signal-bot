from collections import Counter

from app.models import MarketSnapshot
from app.signals.filters import (
    FilterConfig,
    evaluate_candidate_filter,
    is_excluded_us_product,
)
from app.signals.scorer import score_snapshot


RISK_LABELS = {
    "excluded_product": "ETF/레버리지/파생형 상품",
    "price_too_low": "2달러 미만 저가주",
    "volume_too_low": "거래량 증가율 200% 미만",
    "volume_too_high": "거래량 증가율 2000% 초과",
    "trading_value_too_low": "거래대금 5억 미만",
    "change_too_low": "등락률 2% 미만",
    "change_too_high": "등락률 12% 초과",
    "vwap_break": "VWAP 아래 이탈",
    "high_pullback": "고점 대비 3% 초과 이탈",
    "unsupported_market": "미국장 외 시장",
    "other": "기타",
}


def build_rejection_report(
    snapshots: list[MarketSnapshot],
    near_miss_limit: int = 5,
    filter_config: FilterConfig | None = None,
) -> dict:
    filter_config = filter_config or FilterConfig()
    risk_counts: Counter[str] = Counter()
    passed = []
    rejected = []

    for snapshot in snapshots:
        decision = evaluate_candidate_filter(snapshot, filter_config)
        categories = _risk_categories(snapshot, filter_config)
        if not decision.passed and not categories:
            categories = ["other"]

        candidate = score_snapshot(snapshot) if snapshot.market == "US" else None
        row = {
            "market": snapshot.market,
            "symbol": snapshot.symbol,
            "name": snapshot.name,
            "score": candidate.score if candidate else 0,
            "price": snapshot.price,
            "change_pct": snapshot.change_pct,
            "volume_ratio": snapshot.volume_ratio,
            "trading_value_krw": snapshot.trading_value_krw,
        }
        if decision.passed:
            passed.append(row)
        else:
            risk_counts.update(categories)
            rejected.append(
                {
                    **row,
                    "risk_categories": categories,
                    "risk_labels": [RISK_LABELS.get(category, category) for category in categories],
                }
            )

    passed.sort(key=lambda row: row["score"], reverse=True)
    rejected.sort(key=lambda row: (row["score"], -len(row["risk_categories"])), reverse=True)

    return {
        "total": len(snapshots),
        "passed_count": len(passed),
        "rejected_count": len(rejected),
        "risk_counts": dict(risk_counts.most_common()),
        "risk_labels": RISK_LABELS,
        "top_passed": passed[:near_miss_limit],
        "near_misses": rejected[:near_miss_limit],
    }


def _risk_categories(snapshot: MarketSnapshot, config: FilterConfig) -> list[str]:
    if snapshot.market != "US":
        return ["unsupported_market"]

    categories = []
    if is_excluded_us_product(snapshot):
        categories.append("excluded_product")
    if snapshot.price <= 0 or snapshot.price < config.us_min_price:
        categories.append("price_too_low")
    if snapshot.volume_ratio < config.us_volume_ratio_min:
        categories.append("volume_too_low")
    elif snapshot.volume_ratio > config.us_volume_ratio_max:
        categories.append("volume_too_high")
    if snapshot.trading_value_krw < config.us_min_trading_value_krw:
        categories.append("trading_value_too_low")
    if snapshot.change_pct < config.us_change_pct_min:
        categories.append("change_too_low")
    elif snapshot.change_pct > config.us_change_pct_max:
        categories.append("change_too_high")
    if snapshot.vwap_price and snapshot.vwap_price > 0 and snapshot.price < snapshot.vwap_price:
        categories.append("vwap_break")
    if snapshot.high_price and snapshot.high_price > 0:
        high_pullback_pct = ((snapshot.high_price - snapshot.price) / snapshot.high_price) * 100
        if high_pullback_pct > 3:
            categories.append("high_pullback")
    return categories
