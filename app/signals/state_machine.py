UPTREND_ALERT_THRESHOLD_PCT = 1.5


def evaluate_signal_status(
    current_price: float,
    target_price: float,
    stop_price: float,
    last_alert_price: float,
) -> str:
    if current_price >= target_price:
        return "TARGET_REACHED"
    if current_price <= stop_price:
        return "STOPPED"
    if last_alert_price > 0:
        move_pct = ((current_price - last_alert_price) / last_alert_price) * 100
        if move_pct >= UPTREND_ALERT_THRESHOLD_PCT:
            return "UPTREND"
    return "WATCHING"
