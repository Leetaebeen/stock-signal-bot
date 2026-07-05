# Stock Paper Trader

한국투자증권 KIS Open API 모의투자 기반 자동매매 학습 프로젝트입니다.

현재 단계는 **모의투자 연결 + 주문 차단 안전장치 + 거래 이벤트 알림 구조**입니다. 실계좌 주문은 막아두고, 모의투자 주문도 `ORDER_ENABLED=true`와 실행 옵션을 같이 켰을 때만 나가도록 설계합니다.

## 현재 기능

- KIS 모의투자 토큰 발급
- 모의투자 국내 잔고 조회
- 국내/해외 현재가 조회
- 국내/해외 모의 주문 API 연결
- 주문 기본값 차단: `ORDER_ENABLED=false`
- 텔레그램 거래 이벤트 메시지 포맷
- 보안 체크와 테스트

## 환경변수

`.env`에 아래 값을 설정합니다.

```env
KIS_ENV=paper
KIS_APP_KEY=모의투자_APP_KEY
KIS_APP_SECRET=모의투자_APP_SECRET
KIS_ACCOUNT_NO=계좌번호_앞_8자리
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
python -m app.tools.kis_quote_check 005930 --market KR --name 삼성전자
python -m app.tools.kis_quote_check NVDA --market US --exchange NAS --name NVIDIA
python -m app.tools.telegram_test
```

## 주문 드라이런

아래 명령은 실제 주문을 보내지 않습니다.

```powershell
python -m app.tools.kis_order_check KR buy 005930 --qty 1 --price 78000
python -m app.tools.kis_order_check US buy NVDA --qty 1 --price 144.2 --exchange NAS
```

실제 모의 주문 테스트는 나중에 `ORDER_ENABLED=true`로 바꾸고 `--execute`를 붙여서 1주 단위로만 진행합니다.

## 텔레그램 알림 정책

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
- 실계좌 자동주문은 구현하지 않습니다.
