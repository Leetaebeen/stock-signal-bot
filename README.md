# Stock Paper Trader

한국투자증권 KIS Open API 모의투자 기반 자동매매 학습 프로젝트입니다.

현재 단계는 **모의투자 자동매매 + 분봉 모멘텀 진입 + 보유 종목 우선 감시**입니다. 실계좌 주문은 막아두고, 모의투자 주문도 `ORDER_ENABLED=true`일 때만 전송합니다.

## 현재 기능

- KIS 모의투자 토큰 발급
- 모의투자 국내/미국 잔고 조회 및 로컬 상태 동기화
- 국내/해외 현재가 조회
- 국내/해외 1분봉 조회
- 국내 거래대금 순위와 미국 거래량 10만 주 이상 상승률 순위 기반 동적 후보 수집
- 순위 API 장애 시 설정된 종목 목록으로 자동 복귀 및 5분 캐시
- 국내·미국 휴장일 조회와 장 진입 차단
- 국내/해외 모의 주문 및 실제 체결 조회
- 매수 직전 국내/해외 주문 가능 수량 검증
- 120초 이상 미체결 주문 자동 취소 및 최대 3회 재확인
- SQLite 체결·실현손익 거래 저널
- 시장별 최근 24시간 매수 3회·실현손실 한도 및 종목 재진입 대기
- 후보 신호의 전략 지표와 실행 결과 저장
- 신호 발생 5·15·30분 후 수익률 자동 라벨링
- 시장별 학습 준비도 집계와 완료 라벨 CSV 내보내기
- 거래일 단위 학습·검증 분리와 비용 반영 모델 백테스트
- 종목별 NASDAQ/NYSE 거래소 라우팅
- 분봉 거래량, 1분·5분 상승률, 고점 돌파, VWAP 이격 기반 진입
- 익절, 손절, 트레일링 스톱, 최대 보유시간 청산
- 보유 종목을 신규 후보보다 먼저 감시
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

## 매수 기준

먼저 당일 등락률과 거래대금으로 유동성 후보를 고른 뒤 최근 완성된 1분봉을 확인합니다.

- 최근 분봉이 최소 8개 이상 존재
- 완성 1분봉 거래량이 직전 분봉 중앙값보다 크게 증가
- 1분과 5분 가격 흐름이 모두 상승
- 현재가가 직전 5분 고점을 돌파
- 단기 거래량 가중 평균가(VWAP) 위에 있으면서 과도하게 이격되지 않음
- 전체 전략 점수가 `ENTRY_MIN_SCORE` 이상

조건값은 `.env.example`의 `ENTRY_*` 항목으로 조정합니다.

## 확인 명령

```powershell
python -m app.tools.kis_auth_check
python -m app.tools.kis_balance_check
python -m app.tools.kis_quote_check 005930 --market KR --name 삼성전자
python -m app.tools.kis_quote_check NVDA --market US --exchange NAS --name NVIDIA
python -m app.tools.telegram_test
python -m app.tools.trade_summary
python -m app.tools.execution_audit --broker
python -m app.tools.training_export
python -m app.tools.model_backtest
python -m app.tools.kis_buying_power_check KR 005930 78000
python -m app.tools.kis_buying_power_check US NVDA 144.2 --exchange NAS
python -m app.tools.request_liquidation 005930 --market KR
python -m app.tools.request_liquidation 005930 --market KR --confirm
```

## 주문 드라이런

아래 명령은 실제 주문을 보내지 않습니다.

```powershell
python -m app.tools.kis_order_check KR buy 005930 --qty 1 --price 78000
python -m app.tools.kis_order_check US buy NVDA --qty 1 --price 144.2 --exchange NAS
python -m app.tools.kis_order_check US buy NVDA --qty 1 --price 160 --exchange NAS --session day
python -m app.tools.kis_order_check US buy NVDA --qty 1 --price 160 --exchange NAS --session pre
python -m app.tools.kis_order_check US buy NVDA --qty 1 --price 160 --exchange NAS --session after
```

실제 모의 주문 테스트는 `ORDER_ENABLED=true`와 `--execute`를 사용하며 1주 단위로 진행합니다. 미국 주식은 `regular`, `day`, `pre`, `after` 세션을 지원하고 정규장 외에는 지정가만 허용합니다.

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
- 주문 접수만으로 체결 처리하지 않으며 KIS 체결 내역 확인 후 포지션과 알림을 갱신합니다.
- 미체결 취소도 KIS 취소 완료를 확인한 뒤 로컬 상태에서 제거합니다.
- 로컬에 없던 계좌 보유 종목은 자동 매도하지 않는 관리 제외 상태로 반영합니다.
- 모델은 최소 20거래일 검증 기준을 통과하기 전까지 실시간 주문에 사용하지 않습니다.
- 매일 17시 학습셋과 모델 검증을 갱신하되 검증 모델의 주문 적용은 자동으로 하지 않습니다.
