# Stock Signal Bot

개인용 미장 급등주 신호 알림 봇입니다. 자동매매는 하지 않고, 실시간 시장 데이터를 분석해 텔레그램으로 후보 종목을 알려줍니다. 투자 판단과 매매 책임은 사용자 본인에게 있습니다.

## 기능

- KIS API 기반 미장 급등 후보 수집
- 거래량, 등락률, 거래대금, 고가 근접, VWAP 점수화
- SEC EDGAR 공시 리스크 확인
- Gemini AI 최종 판단: `BUY`, `WATCH`, `SKIP`
- AI 캐시, 최소 점수, 일일 호출 제한
- 텔레그램 알림, 목표가/손절가/상승세 추적
- 5/15/30/60분 성과 추적 데이터 저장

## 설치

```powershell
cd D:\Stock_toss
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env`에 API 키를 입력해야 실제로 동작합니다. `.env`는 Git에 올리면 안 됩니다.

## 주요 환경변수

```env
MARKET_MODE=kis_rank
ENABLED_MARKETS=US
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
KIS_APP_KEY=
KIS_APP_SECRET=
KIS_ACCOUNT_NO=
KIS_ENV=real
SEC_USER_AGENT=stock-signal-bot/0.1 your-email@example.com
AI_ANALYSIS_ENABLED=true
AI_PROVIDER=gemini
AI_API_KEY=
AI_MODEL=gemini-2.5-flash-lite
SCAN_INTERVAL_SECONDS=180
MIN_ALERT_SCORE=80
ALERT_COOLDOWN_MINUTES=60
AI_MIN_CONFIDENCE=75
AI_MIN_RULE_SCORE=85
AI_CACHE_TTL_MINUTES=60
AI_DAILY_LIMIT=100
OUTCOME_HORIZON_MINUTES=5,15,30,60
```

`ENABLED_MARKETS=US`가 기본값입니다. 국장을 다시 켜려면 `KR,US`로 바꾸면 됩니다.

## 확인

```powershell
python -m app.tools.kis_auth_check
python -m app.tools.ai_check
python -m app.tools.deploy_check
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

## Git 보안

`.env`, `.venv/`, `data/kis_token*.json`, `data/signals.db`, `logs/`, 캐시 파일은 `.gitignore`로 제외됩니다.

공개 저장소에 올리기 전 항상 확인하세요.

```powershell
python -m app.tools.security_check
git add --dry-run .
```
