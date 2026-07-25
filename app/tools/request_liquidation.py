import argparse

from app.config import get_settings
from app.trading.state import JsonPositionStore


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Queue an existing paper-account position for liquidation at the next active session."
    )
    parser.add_argument("symbol", help="Stock symbol, for example 005930 or NVDA")
    parser.add_argument("--market", choices=("KR", "US"), required=True)
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Persist the liquidation request. Without this flag, only a preview is shown.",
    )
    args = parser.parse_args()

    settings = get_settings()
    _assert_paper_only(settings)
    store = JsonPositionStore(settings.trading_state_path)
    symbol = args.symbol.strip().upper()
    position = store.load().get(symbol)
    if position is None:
        raise SystemExit(f"포지션을 찾을 수 없습니다: {symbol}")
    if position.market.upper() != args.market:
        raise SystemExit(
            f"시장 정보가 일치하지 않습니다: 저장={position.market}, 입력={args.market}"
        )

    print(f"종목: {position.name} ({position.symbol})")
    print(f"시장: {position.market}")
    print(f"수량: {position.quantity:g}")
    print(f"평균 매수가: {position.entry_price:,.2f}")
    if not args.confirm:
        print("미리보기만 수행했습니다. 청산 예약은 등록되지 않았습니다.")
        print("등록하려면 같은 명령에 --confirm을 추가하세요.")
        return

    requested = store.request_liquidation(symbol, args.market)
    print("모의 포지션 청산 요청을 등록했습니다.")
    print("현재 주문은 전송하지 않았으며, 다음 활성 장에서 매도 주문을 제출합니다.")
    print(f"청산 요청 상태: {requested.liquidation_requested}")


def _assert_paper_only(settings) -> None:
    if settings.kis_env.strip().lower() != "paper":
        raise SystemExit("KIS_ENV=paper 환경에서만 청산 요청을 등록할 수 있습니다.")
    if not settings.paper_trading_only:
        raise SystemExit("PAPER_TRADING_ONLY=true가 필요합니다.")
    if settings.real_trading_enabled:
        raise SystemExit("REAL_TRADING_ENABLED=true에서는 실행할 수 없습니다.")


if __name__ == "__main__":
    main()
