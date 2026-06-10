from app.models import MarketSnapshot, SignalCandidate


def score_snapshot(snapshot: MarketSnapshot) -> SignalCandidate:
    if snapshot.market == "KR":
        return _score_kr(snapshot)
    return _score_us(snapshot)


def _score_kr(snapshot: MarketSnapshot) -> SignalCandidate:
    score = 0
    reasons: list[str] = []
    risks: list[str] = []

    if snapshot.volume_ratio >= 5:
        score += 30
        reasons.append("거래량이 기준 대비 5배 이상 급증")
    elif snapshot.volume_ratio >= 3.5:
        score += 22
        reasons.append("거래량이 기준 대비 3.5배 이상 증가")
    elif snapshot.volume_ratio >= 2.5:
        score += 12
        reasons.append("거래량 증가 확인")
    else:
        risks.append("거래량 강도 추가 확인 필요")

    if 4 <= snapshot.change_pct <= 11:
        score += 20
        reasons.append("등락률이 단타 관심 구간에 위치")
    elif 2 <= snapshot.change_pct < 4:
        score += 10
        reasons.append("초기 상승 구간")
    elif 11 < snapshot.change_pct <= 18:
        score += 5
        risks.append("이미 많이 오른 구간이라 추격 주의")
    elif snapshot.change_pct < 0:
        score -= 20
        risks.append("당일 상승 모멘텀 부족")

    if snapshot.trading_value_krw >= 150_000_000_000:
        score += 25
        reasons.append("거래대금이 매우 강함")
    elif snapshot.trading_value_krw >= 80_000_000_000:
        score += 18
        reasons.append("거래대금이 충분함")
    elif snapshot.trading_value_krw >= 30_000_000_000:
        score += 8
        reasons.append("최소 거래대금 조건 충족")
    else:
        score -= 30
        risks.append("거래대금 부족")

    score += _score_intraday_strength(snapshot, reasons, risks)

    if snapshot.vi_gap_pct is not None and snapshot.vi_gap_pct <= 2:
        score += 15
        reasons.append("상승 VI 근접")
    elif snapshot.vi_gap_pct is not None and snapshot.vi_gap_pct <= 4:
        score += 8
        reasons.append("VI 접근 구간")

    flow = snapshot.foreign_flow_score + snapshot.institution_flow_score + snapshot.program_flow_score
    if flow >= 1.2:
        score += 15
        reasons.append("외국인/기관/프로그램 수급이 동시에 양호함")
    elif flow >= 0.7:
        score += 8
        reasons.append("수급 개선 흐름")
    elif flow < 0:
        score -= 15
        risks.append("수급 흐름 약함")

    if snapshot.disclosure_risk > 0:
        penalty = min(50, int(snapshot.disclosure_risk * 5))
        score -= penalty
        risks.append("최근 공시 리스크 감지")

    return SignalCandidate(snapshot=snapshot, score=max(0, score), reasons=reasons, risks=risks)


def _score_us(snapshot: MarketSnapshot) -> SignalCandidate:
    score = 0
    reasons: list[str] = []
    risks: list[str] = []

    if snapshot.volume_ratio >= 6:
        score += 30
        reasons.append("상대 거래량이 6배 이상 급증")
    elif snapshot.volume_ratio >= 4:
        score += 22
        reasons.append("상대 거래량이 4배 이상 증가")
    elif snapshot.volume_ratio >= 2.5:
        score += 12
        reasons.append("상대 거래량 증가")
    else:
        risks.append("상대 거래량 추가 확인 필요")

    if 3 <= snapshot.change_pct <= 9:
        score += 20
        reasons.append("상승률이 단기 모멘텀 구간에 위치")
    elif 1.5 <= snapshot.change_pct < 3:
        score += 10
        reasons.append("초기 모멘텀 확인")
    elif 9 < snapshot.change_pct <= 18:
        score += 5
        risks.append("갭상승 또는 급등 이후 추격 주의")
    elif snapshot.change_pct < 0:
        score -= 20
        risks.append("당일 모멘텀 약함")

    if snapshot.trading_value_krw >= 1_500_000_000_000:
        score += 25
        reasons.append("달러 거래대금이 매우 강함")
    elif snapshot.trading_value_krw >= 800_000_000_000:
        score += 18
        reasons.append("달러 거래대금이 충분함")
    elif snapshot.trading_value_krw >= 300_000_000_000:
        score += 8
        reasons.append("최소 유동성 조건 충족")
    else:
        score -= 30
        risks.append("유동성 부족")

    score += _score_intraday_strength(snapshot, reasons, risks)

    if snapshot.news_score >= 0.75:
        score += 15
        reasons.append("뉴스 또는 이벤트 모멘텀 강함")
    elif snapshot.news_score >= 0.4:
        score += 8
        reasons.append("확인 가능한 이벤트 모멘텀")

    if snapshot.disclosure_risk > 0:
        penalty = min(50, int(snapshot.disclosure_risk * 6))
        score -= penalty
        risks.append("SEC 공시 또는 이벤트 리스크 감지")

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
            reasons.append("고가 근처에서 강하게 유지")
        elif high_pullback_pct <= 3:
            score_delta += 8
            reasons.append("고가 대비 3% 이내 유지")
        else:
            score_delta -= 15
            risks.append("고가 대비 이탈폭이 큼")

    if snapshot.vwap_price and snapshot.vwap_price > 0:
        if snapshot.price >= snapshot.vwap_price:
            score_delta += 15
            reasons.append("VWAP 위에서 유지")
        else:
            score_delta -= 20
            risks.append("VWAP 아래로 이탈")
    return score_delta
