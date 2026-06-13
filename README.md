# Stock Signal Bot

개인용 미국 주식 급등주 텔레그램 알림 봇입니다.
토스증권 Open API로 시세를 확인하고, 자동주문은 절대 실행하지 않습니다.

## 기능

- 토스증권 Open API 기반 미국 주식 현재가 조회
- Nasdaq Trader 심볼 목록 기반 미국 종목 감시
- 1분/5분/20분 급등 감지
- 거래량 증가율, 상승률, 거래대금, 가격 조건 필터
- 거래량 +90% 이상 붙은 급등주만 알림
- 한국어 종목명 우선 표시
- 현재가 원화 표시
- 텔레그램 한글 알림

## 설치

```powershell
cd D:\Stock_toss
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env`에는 실제 키를 직접 넣습니다. `.env`, 토큰 캐시, DB, SSH 키는 깃에 올리지 않습니다.

## 주요 환경변수

```env
MARKET_MODE=toss_rank
ENABLED_MARKETS=US
SCAN_INTERVAL_SECONDS=60
MIN_ALERT_SCORE=70
ALERT_COOLDOWN_MINUTES=60

TOSS_API_KEY=
TOSS_SECRET_KEY=
TOSS_BASE_URL=https://openapi.tossinvest.com
TOSS_TOKEN_CACHE_PATH=data/toss_token.json
TOSS_SCAN_CURSOR_PATH=data/toss_scan_cursor.txt
TOSS_SPIKE_CACHE_PATH=data/toss_price_cache.json
TOSS_REQUEST_INTERVAL_SECONDS=1.1
TOSS_RANK_COUNT=40
TOSS_PRICE_SWEEP_COUNT=0
TOSS_SPIKE_1M_PCT=3.0
TOSS_SPIKE_5M_PCT=8.0
TOSS_SPIKE_20M_PCT=15.0
TOSS_SPIKE_MAX_CANDIDATES=20
US_SYMBOLS_PATH=data/us_symbols.txt

TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

SEC_USER_AGENT=stock-signal-bot/0.1 your-email@example.com
US_FILTER_VOLUME_RATIO_MIN=2.0
US_FILTER_VOLUME_RATIO_MAX=20.0
US_FILTER_CHANGE_PCT_MIN=2.0
US_FILTER_CHANGE_PCT_MAX=12.0
US_FILTER_MIN_TRADING_VALUE_KRW=500000000
US_FILTER_MIN_PRICE=2.0
```

## 확인

```powershell
python -m app.tools.us_universe_download
python -m app.tools.toss_config_check
python -m app.tools.toss_auth_check
python -m app.tools.toss_price_check NVDA
python -m app.tools.toss_us_scan_check --count 40
python -m app.tools.security_check
```

## 실행

```powershell
.\scripts\run_once.ps1
.\scripts\run_worker.ps1
.\scripts\start_worker_bg.ps1
.\scripts\worker_status.ps1
.\scripts\stop_worker.ps1
```

## 알림 예시

```text
[급등주 포착 알림]
------------------------------
종목명: 엔비디아 (NVDA)
현재가: 284,123원
상승률: +8.55%
거래량: 4.20배
자동주문은 실행하지 않습니다.
```

## 테스트

```powershell
.\scripts\test_all.ps1
```
