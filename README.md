# Stock Signal Bot

개인용 미국 주식 급등 후보 텔레그램 알림 봇입니다.
자동매매/자동주문 기능은 넣지 않습니다. 매수와 매도 판단은 사용자가 직접 합니다.

## 기능

- 토스증권 Open API 기반 미국 주식 시세 조회
- Nasdaq Trader 심볼 목록 기반 미국 종목 롤링 스캔
- 거래량 증가율, 등락률, 거래대금, 고가 근접, VWAP 조건 필터
- SEC 공시 리스크 확인
- Gemini AI 최종 판단: `BUY`, `WATCH`, `SKIP`
- 텔레그램 종목 포착, 상승세, 목표가 도달, 손절가 이탈 알림
- 5/15/30/60분 성과 추적 저장

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

TOSS_API_KEY=
TOSS_SECRET_KEY=
TOSS_BASE_URL=https://openapi.tossinvest.com
TOSS_TOKEN_CACHE_PATH=data/toss_token.json
TOSS_SCAN_CURSOR_PATH=data/toss_scan_cursor.txt
TOSS_REQUEST_INTERVAL_SECONDS=1.1
TOSS_RANK_COUNT=40
US_SYMBOLS_PATH=data/us_symbols.txt

TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

SEC_USER_AGENT=stock-signal-bot/0.1 your-email@example.com
AI_ANALYSIS_ENABLED=true
AI_ANALYSIS_REQUIRED=true
AI_PROVIDER=gemini
AI_API_KEY=
AI_MODEL=gemini-2.5-flash-lite

SCAN_INTERVAL_SECONDS=60
MIN_ALERT_SCORE=80
ALERT_COOLDOWN_MINUTES=60
US_FILTER_VOLUME_RATIO_MIN=2.0
US_FILTER_VOLUME_RATIO_MAX=20.0
US_FILTER_CHANGE_PCT_MIN=2.0
US_FILTER_CHANGE_PCT_MAX=12.0
US_FILTER_MIN_TRADING_VALUE_KRW=500000000
US_FILTER_MIN_PRICE=2.0
AI_MIN_CONFIDENCE=75
AI_MIN_RULE_SCORE=85
AI_CACHE_TTL_MINUTES=60
AI_DAILY_LIMIT=100
OUTCOME_HORIZON_MINUTES=5,15,30,60
```

`TOSS_RANK_COUNT`는 한 사이클에 검사할 종목 수입니다. `data/toss_scan_cursor.txt`가 다음 검사 위치를 저장해 전체 심볼을 순환합니다.

## 확인

```powershell
python -m app.tools.us_universe_download
python -m app.tools.toss_config_check
python -m app.tools.toss_auth_check
python -m app.tools.toss_price_check NVDA --name NVIDIA
python -m app.tools.toss_us_scan_check --count 20
python -m app.tools.ai_check
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

## 조회

```powershell
python -m app.tools.active_signals
python -m app.tools.ai_history --limit 10
python -m app.tools.outcome_history --limit 20
python -m app.tools.clear_signals --yes
```

## 테스트

```powershell
.\scripts\test_all.ps1
```
