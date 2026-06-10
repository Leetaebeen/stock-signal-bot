from app.models import SignalCandidate, TradePlan


def build_trade_plan(candidate: SignalCandidate) -> TradePlan:
    snapshot = candidate.snapshot
    entry_price = _round_price(snapshot.market, snapshot.price)

    if snapshot.market == "KR":
        target_pct = _kr_target_pct(snapshot.change_pct)
        stop_pct = 2.0
    else:
        target_pct = _us_target_pct(snapshot.change_pct)
        stop_pct = 2.5

    target_price = _round_price(snapshot.market, entry_price * (1 + target_pct / 100))
    stop_price = _round_price(snapshot.market, entry_price * (1 - stop_pct / 100))
    return TradePlan(
        entry_price=entry_price,
        current_price=snapshot.price,
        target_price=target_price,
        stop_price=stop_price,
        expected_profit_pct=target_pct,
        stop_loss_pct=stop_pct,
    )


def _kr_target_pct(change_pct: float) -> float:
    if change_pct >= 9:
        return 2.2
    if change_pct >= 6:
        return 3.0
    return 3.8


def _us_target_pct(change_pct: float) -> float:
    if change_pct >= 8:
        return 2.5
    if change_pct >= 5:
        return 3.2
    return 4.0


def _round_price(market: str, price: float) -> float:
    if market == "US":
        return round(price, 2)
    if price < 2_000:
        unit = 1
    elif price < 5_000:
        unit = 5
    elif price < 20_000:
        unit = 10
    elif price < 50_000:
        unit = 50
    elif price < 200_000:
        unit = 100
    elif price < 500_000:
        unit = 500
    else:
        unit = 1_000
    return round(price / unit) * unit
