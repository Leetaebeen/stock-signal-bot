# Stock Paper Trader

한국투자증권 KIS Open API 모의투자 전용 자동매매 학습 프로젝트입니다.

현재 단계는 **모의투자 읽기 전용 연결 + 거래 이벤트 알림 기반**입니다.

- KIS 모의투자 토큰 발급
- 모의투자 계좌 잔고 조회
- 국내/해외 현재가 조회
- 텔레그램 거래 이벤트 알림
- 실계좌 주문 차단
- 실제 주문 API 미구현

## 환경변수

`.env`에 아래 값을 넣습니다.

```env
KIS_ENV=paper
KIS_APP_KEY=모의투자_APP_KEY
KIS_APP_SECRET=모의투자_APP_SECRET
KIS_ACCOUNT_NO=계좌번호_앞8자리
KIS_ACCOUNT_PRODUCT_CODE=계좌상품코드_2자리
KIS_TOKEN_CACHE_PATH=data/kis_token_paper.json

TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=텔레그램_BOT_TOKEN
TELEGRAM_CHAT_ID=텔레그램_CHAT_ID
TELEGRAM_NOTIFY_STARTUP=false
TELEGRAM_NOTIFY_SIGNALS=false
TELEGRAM_NOTIFY_TRADES=true
TELEGRAM_NOTIFY_ERRORS=true

PAPER_TRADING_ONLY=true
ORDER_ENABLED=false
REAL_TRADING_ENABLED=false
```

## 확인 명령

```powershell
python -m app.tools.kis_auth_check
python -m app.tools.kis_balance_check
python -m app.tools.kis_quote_check NVDA --market US --exchange NAS --name NVIDIA
python -m app.tools.kis_quote_check 005930 --market KR --name 삼성전자
python -m app.tools.telegram_test
```

## 알림 정책

자동 실행 중 텔레그램은 거래 이벤트에만 사용합니다.

- 모의 매수 체결
- 모의 매도 체결
- 주문 실패
- 긴급 오류

봇 시작, 감시 시작, 후보 포착, 단순 현재가 알림은 보내지 않습니다.

## 안전 원칙

- `KIS_ENV=paper`만 허용합니다.
- `PAPER_TRADING_ONLY=true`가 아니면 중단합니다.
- `REAL_TRADING_ENABLED=true`면 중단합니다.
- `ORDER_ENABLED=false`가 기본값입니다.
- 주문 API는 아직 구현하지 않습니다.
