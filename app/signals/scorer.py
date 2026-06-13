from app.models import MarketSnapshot, SignalCandidate


def score_snapshot(snapshot: MarketSnapshot) -> SignalCandidate:
    if snapshot.market != "US":
        raise RuntimeError("Only US market snapshots are supported.")

    score = 0
    reasons: list[str] = []
    risks: list[str] = []
    explosion_candidate = (
        12 < snapshot.change_pct <= 300
        and snapshot.volume_ratio >= 1.9
        and snapshot.trading_value_krw >= 100_000_000
        and snapshot.price >= 0.1
    )

    if explosion_candidate and snapshot.volume_ratio < 2:
        score += 18
        reasons.append(f"초급등 거래량 증가 {snapshot.volume_ratio:.2f}배")
    elif 4 <= snapshot.volume_ratio <= 12:
        score += 32
        reasons.append(f"거래량 증가율 {snapshot.volume_ratio * 100:.0f}%")
    elif 2 <= snapshot.volume_ratio < 4:
        score += 22
        reasons.append(f"거래량 증가율 {snapshot.volume_ratio * 100:.0f}%")
    elif 12 < snapshot.volume_ratio <= 20:
        score += 18
        reasons.append(f"거래량 증가율 {snapshot.volume_ratio * 100:.0f}%")
        risks.append("거래량 급증이 매우 커 변동성 주의")
    elif snapshot.volume_ratio > 20:
        score -= 25
        risks.append("거래량 증가율 2000% 초과")
    else:
        score -= 20
        risks.append("거래량 증가율 200% 미만")

    if 3 <= snapshot.change_pct <= 8:
        score += 28
        reasons.append("상승률이 급등 초입 구간")
    elif 2 <= snapshot.change_pct < 3:
        score += 18
        reasons.append("초기 상승 모멘텀")
    elif 8 < snapshot.change_pct <= 12:
        score += 12
        reasons.append("강한 상승 모멘텀")
        risks.append("이미 빠르게 오른 구간")
    elif 12 < snapshot.change_pct <= 300 and snapshot.volume_ratio >= 1.9:
        score += 30
        reasons.append("초급등 포착 구간")
        risks.append("변동성과 거래정지 위험 주의")
    elif snapshot.change_pct > 12:
        score -= 30
        risks.append("상승률 과열 또는 거래량 부족")
    elif snapshot.change_pct < 0:
        score -= 20
        risks.append("상승 모멘텀 약함")

    if snapshot.trading_value_krw >= 30_000_000_000:
        score += 25
        reasons.append("거래대금 매우 강함")
    elif snapshot.trading_value_krw >= 10_000_000_000:
        score += 18
        reasons.append("거래대금 충분")
    elif snapshot.trading_value_krw >= 5_000_000_000:
        score += 12
        reasons.append("거래대금 조건 충족")
    elif snapshot.trading_value_krw >= 500_000_000:
        score += 6
        reasons.append("최소 유동성 통과")
    else:
        score -= 30
        risks.append("거래대금 부족")

    score += _score_intraday_strength(snapshot, reasons, risks)

    if snapshot.news_score >= 0.75:
        score += 12
        reasons.append("뉴스 또는 이벤트 모멘텀 강함")
    elif snapshot.news_score >= 0.4:
        score += 6
        reasons.append("확인 가능한 이벤트 모멘텀")

    if snapshot.disclosure_risk > 0:
        penalty = min(50, int(snapshot.disclosure_risk * 6))
        score -= penalty
        risks.append("SEC 공시 리스크 감지")

    return SignalCandidate(snapshot=snapshot, score=max(0, score), reasons=reasons, risks=risks)


def _score_intraday_strength(
    snapshot: MarketSnapshot,
    reasons: list[str],
    risks: list[str],
) -> int:
    score_delta = 0
    if snapshot.high_price and snapshot.high_price > 0:
        high_pullback_pct = ((snapshot.high_price - snapshot.price) / snapshot.high_price) * 100
        if high_pullback_pct <= 1:
            score_delta += 15
            reasons.append("고가 근처에서 유지")
        elif high_pullback_pct <= 3:
            score_delta += 8
            reasons.append("고가 대비 3% 이내 유지")
        else:
            score_delta -= 15
            risks.append("고가 대비 이탈폭 큼")

    if snapshot.vwap_price and snapshot.vwap_price > 0:
        if snapshot.price >= snapshot.vwap_price:
            score_delta += 18
            reasons.append("VWAP 위에서 유지")
        else:
            score_delta -= 30
            risks.append("VWAP 아래로 이탈")
    return score_delta
