from app.models import SignalCandidate
from app.signals.trade_plan import build_trade_plan


def build_scan_start_message(market_name: str) -> str:
    return (
        f"[{market_name} 감시 시작]\n"
        "AI 종목 포착을 시작합니다.\n\n"
        "강한 신호가 확인되면 최종 1개 종목만 텔레그램으로 보냅니다.\n"
        "매매 판단과 주문은 직접 진행하세요."
    )


def build_signal_message(candidate: SignalCandidate) -> str:
    plan = build_trade_plan(candidate)
    snap = candidate.snapshot
    reasons = "\n".join(f"- {reason}" for reason in candidate.reasons) or "- 추천 근거 없음"
    risks = "\n".join(f"- {risk}" for risk in candidate.risks) or "- 현재 기준 주요 리스크 없음"
    ai_text = _format_ai_analysis(candidate)

    return (
        "[AI 종목포착 시그널]\n"
        "------------------------------\n"
        f"포착 종목명: {snap.name} ({snap.symbol})\n"
        f"적정 매수가: {_format_price(snap.market, plan.entry_price)} "
        f"-> {plan.expected_profit_pct:.2f}% 목표\n"
        f"포착 현재가: {_format_price(snap.market, snap.price)} "
        f"-> {snap.change_pct:+.2f}%\n"
        f"목표가: {_format_price(snap.market, plan.target_price)}\n"
        f"손절 기준: {_format_price(snap.market, plan.stop_price)} "
        f"(-{plan.stop_loss_pct:.1f}%)\n"
        f"신호 점수: {candidate.score}점\n\n"
        f"{ai_text}"
        f"추천 근거:\n{reasons}\n\n"
        f"주의 사항:\n{risks}"
    )


def build_uptrend_message(candidate: SignalCandidate, previous_price: float) -> str:
    plan = build_trade_plan(candidate)
    snap = candidate.snapshot
    move_pct = ((snap.price - previous_price) / previous_price) * 100 if previous_price else 0

    return (
        "[상승세 알림]\n"
        "------------------------------\n"
        f"종목명: {snap.name} ({snap.symbol})\n"
        f"이전 기준가: {_format_price(snap.market, previous_price)}\n"
        f"현재가: {_format_price(snap.market, snap.price)} "
        f"-> {snap.change_pct:+.2f}%\n"
        f"추가 상승률: {move_pct:+.2f}%\n"
        f"목표가: {_format_price(snap.market, plan.target_price)}"
    )


def build_target_reached_message(candidate: SignalCandidate) -> str:
    plan = build_trade_plan(candidate)
    snap = candidate.snapshot
    return (
        "[목표가 알림]\n"
        "------------------------------\n"
        f"종목명: {snap.name} ({snap.symbol})\n"
        f"현재가: {_format_price(snap.market, snap.price)} "
        f"-> {snap.change_pct:+.2f}%\n"
        f"적정 목표가 {_format_price(snap.market, plan.target_price)} 도달"
    )


def build_state_uptrend_message(state: dict, current_price: float, change_pct: float) -> str:
    market = state["market"]
    previous_price = float(state["last_alert_price"])
    move_pct = ((current_price - previous_price) / previous_price) * 100 if previous_price else 0
    return (
        "[상승세 알림]\n"
        "------------------------------\n"
        f"종목명: {state['name']} ({state['symbol']})\n"
        f"이전 기준가: {_format_price(market, previous_price)}\n"
        f"현재가: {_format_price(market, current_price)} -> {change_pct:+.2f}%\n"
        f"추가 상승률: {move_pct:+.2f}%\n"
        f"목표가: {_format_price(market, float(state['target_price']))}"
    )


def build_state_target_reached_message(state: dict, current_price: float, change_pct: float) -> str:
    market = state["market"]
    return (
        "[목표가 알림]\n"
        "------------------------------\n"
        f"종목명: {state['name']} ({state['symbol']})\n"
        f"현재가: {_format_price(market, current_price)} -> {change_pct:+.2f}%\n"
        f"적정 목표가 {_format_price(market, float(state['target_price']))} 도달"
    )


def build_state_stop_message(state: dict, current_price: float, change_pct: float) -> str:
    market = state["market"]
    return (
        "[손절 기준 이탈]\n"
        "------------------------------\n"
        f"종목명: {state['name']} ({state['symbol']})\n"
        f"현재가: {_format_price(market, current_price)} -> {change_pct:+.2f}%\n"
        f"손절 기준: {_format_price(market, float(state['stop_price']))}\n"
        "추가 추격은 보류하고 직접 판단하세요."
    )


def _format_ai_analysis(candidate: SignalCandidate) -> str:
    analysis = candidate.ai_analysis
    if analysis is None:
        return ""

    points = "\n".join(f"- {point}" for point in analysis.key_points)
    risk_notes = "\n".join(f"- {risk}" for risk in analysis.risk_notes)
    return (
        "[AI 최종 판단]\n"
        f"판단: {analysis.recommendation}\n"
        f"신뢰도: {analysis.confidence}점\n"
        f"요약: {analysis.summary}\n"
        f"핵심 근거:\n{points or '- 없음'}\n"
        f"AI 리스크:\n{risk_notes or '- 없음'}\n\n"
    )


def _format_price(market: str, price: float) -> str:
    if market == "US":
        return f"${price:,.2f}"
    return f"{price:,.0f}원"
