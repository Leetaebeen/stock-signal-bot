from decimal import Decimal, ROUND_HALF_UP

from app.models import SignalCandidate
from app.signals.trade_plan import build_trade_plan


USD_KRW_RATE = 1350.0


def build_scan_start_message(market_name: str) -> str:
    return (
        f"[{market_name} 감시 시작]\n"
        "급등 포착 레이더를 시작합니다.\n"
        "조건과 AI 판단을 통과한 최종 후보만 알림으로 보냅니다.\n"
        "자동주문은 실행하지 않습니다."
    )


def build_signal_message(candidate: SignalCandidate) -> str:
    plan = build_trade_plan(candidate)
    snap = candidate.snapshot
    ai_text = _format_ai_analysis(candidate)
    reasons = _format_list(candidate.reasons, empty="주요 포착 근거 없음")
    risks = _format_list(candidate.risks, empty="현재 기준 주요 위험 없음")

    return (
        "[급등 후보 포착]\n"
        "------------------------------\n"
        f"종목명: {snap.name} ({snap.symbol})\n"
        f"거래소: {snap.exchange or '-'}\n"
        f"매수가: {_format_price(snap.market, plan.entry_price)}\n"
        f"{_format_current_line(snap.market, snap.price, snap.change_pct)}\n"
        f"목표가: {_format_price(snap.market, plan.target_price)} (+{plan.expected_profit_pct:.2f}%)\n"
        f"손절가: {_format_price(snap.market, plan.stop_price)} (-{plan.stop_loss_pct:.1f}%)\n"
        f"거래량 증가: {snap.volume_ratio:.2f}배\n"
        f"거래대금: {_format_krw(snap.trading_value_krw)}\n"
        f"신호 점수: {candidate.score}점\n\n"
        f"{ai_text}"
        "[포착 근거]\n"
        f"{reasons}\n\n"
        "[주의 사항]\n"
        f"{risks}\n\n"
        "자동매매 알림이 아닙니다. 주문 여부는 직접 판단하세요."
    )


def build_uptrend_message(candidate: SignalCandidate, previous_price: float) -> str:
    plan = build_trade_plan(candidate)
    snap = candidate.snapshot
    move_pct = ((snap.price - previous_price) / previous_price) * 100 if previous_price else 0

    return (
        "[상승세 알림]\n"
        "------------------------------\n"
        f"종목명: {snap.name} ({snap.symbol})\n"
        f"이전 알림가: {_format_price(snap.market, previous_price)}\n"
        f"{_format_current_line(snap.market, snap.price, snap.change_pct)}\n"
        f"추가 상승: {move_pct:+.2f}%\n"
        f"목표가: {_format_price(snap.market, plan.target_price)}\n"
        f"손절가: {_format_price(snap.market, plan.stop_price)}"
    )


def build_target_reached_message(candidate: SignalCandidate) -> str:
    plan = build_trade_plan(candidate)
    snap = candidate.snapshot
    return (
        "[목표가 도달]\n"
        "------------------------------\n"
        f"종목명: {snap.name} ({snap.symbol})\n"
        f"{_format_current_line(snap.market, snap.price, snap.change_pct)}\n"
        f"목표가 {_format_price(snap.market, plan.target_price)}에 도달했습니다."
    )


def build_state_uptrend_message(state: dict, current_price: float, change_pct: float) -> str:
    market = state["market"]
    previous_price = float(state["last_alert_price"])
    move_pct = ((current_price - previous_price) / previous_price) * 100 if previous_price else 0
    return (
        "[상승세 알림]\n"
        "------------------------------\n"
        f"종목명: {state['name']} ({state['symbol']})\n"
        f"이전 알림가: {_format_price(market, previous_price)}\n"
        f"{_format_current_line(market, current_price, change_pct)}\n"
        f"추가 상승: {move_pct:+.2f}%\n"
        f"목표가: {_format_price(market, float(state['target_price']))}\n"
        f"손절가: {_format_price(market, float(state['stop_price']))}"
    )


def build_state_target_reached_message(state: dict, current_price: float, change_pct: float) -> str:
    market = state["market"]
    target_price = float(state["target_price"])
    return (
        "[목표가 도달]\n"
        "------------------------------\n"
        f"종목명: {state['name']} ({state['symbol']})\n"
        f"{_format_current_line(market, current_price, change_pct)}\n"
        f"목표가 {_format_price(market, target_price)}에 도달했습니다."
    )


def build_state_stop_message(state: dict, current_price: float, change_pct: float) -> str:
    market = state["market"]
    stop_price = float(state["stop_price"])
    return (
        "[손절가 이탈]\n"
        "------------------------------\n"
        f"종목명: {state['name']} ({state['symbol']})\n"
        f"{_format_current_line(market, current_price, change_pct)}\n"
        f"손절가 {_format_price(market, stop_price)} 이탈\n"
        "추가 추격은 보류하고 직접 판단하세요."
    )


def _format_ai_analysis(candidate: SignalCandidate) -> str:
    analysis = candidate.ai_analysis
    if analysis is None:
        return ""

    points = _format_list(analysis.key_points, empty="없음")
    risk_notes = _format_list(analysis.risk_notes, empty="없음")
    return (
        "[AI 판단]\n"
        f"판정: {analysis.recommendation}\n"
        f"확신도: {analysis.confidence}점\n"
        f"요약: {analysis.summary}\n"
        f"핵심 근거:\n{points}\n"
        f"AI 위험 메모:\n{risk_notes}\n\n"
    )


def _format_list(items: list[str], empty: str) -> str:
    if not items:
        return f"- {empty}"
    return "\n".join(f"- {item}" for item in items)


def _format_price(market: str, price: float) -> str:
    if price <= 0:
        return "가격 확인 실패"
    if market == "US":
        return f"{_round_won(price * USD_KRW_RATE):,}원"
    return f"{price:,.0f}원"


def _format_krw(value: float) -> str:
    if value <= 0:
        return "확인 실패"
    if value >= 100_000_000:
        return f"{value / 100_000_000:,.0f}억 원"
    return f"{_round_won(value):,}원"


def _format_current_line(market: str, price: float, change_pct: float) -> str:
    if price <= 0:
        return "현재가: 가격 확인 실패"
    return f"현재가: {_format_price(market, price)} ({change_pct:+.2f}%)"


def _round_won(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
