# Stock Signal Bot

개인용 주식 신호 알림 봇입니다. 자동매매는 하지 않고, 실시간 시장 데이터를 분석해 텔레그램으로 후보 종목을 알려줍니다.

## 주요 기능

- 한국투자증권 KIS API 기반 국장/미장 데이터 수집
- 거래량, 등락률, 거래대금, 고가 근접, VWAP 기준 점수화
- Open DART 공시 리스크 확인
- SEC EDGAR 공시 리스크 확인
- Gemini AI 최종 판단: `BUY`, `WATCH`, `SKIP`
- AI 호출 캐시, 최소 점수, 일일 호출 제한
- 텔레그램 알림
- 목표가, 손절가, 상승세 추적
- 5/15/30/60분 성과 추적 데이터 저장
- 로컬 백그라운드 실행 스크립트 제공

## 주의

이 프로젝트는 개인 참고용입니다. 투자 판단과 매매 책임은 사용자 본인에게 있습니다.

## 설치

```powershell
cd D:\Stock_toss
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env`에 API 키를 입력해야 실제로 동작합니다. `.env`는 Git에 올리면 안 됩니다.

## 필수 환경변수

```env
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

KIS_APP_KEY=
KIS_APP_SECRET=
KIS_ACCOUNT_NO=
KIS_ENV=real

DART_API_KEY=
SEC_USER_AGENT=stock-signal-bot/0.1 your-email@example.com

AI_ANALYSIS_ENABLED=true
AI_PROVIDER=gemini
AI_API_KEY=
AI_MODEL=gemini-2.5-flash-lite
```

## 권장 운영값

```env
SCAN_INTERVAL_SECONDS=180
MIN_ALERT_SCORE=80
ALERT_COOLDOWN_MINUTES=60
AI_MIN_CONFIDENCE=75
AI_MIN_RULE_SCORE=85
AI_CACHE_TTL_MINUTES=60
AI_DAILY_LIMIT=100
OUTCOME_HORIZON_MINUTES=5,15,30,60
```

## 확인 명령

```powershell
python -m app.tools.kis_auth_check
python -m app.tools.ai_check
python -m app.tools.deploy_check
python -m app.tools.security_check
```

## 실행

```powershell
# 한 번만 스캔
.\scripts\run_once.ps1

# 터미널에서 계속 실행
.\scripts\run_worker.ps1

# 백그라운드 실행
.\scripts\start_worker_bg.ps1

# 백그라운드 상태 확인
.\scripts\worker_status.ps1

# 백그라운드 중지
.\scripts\stop_worker.ps1
```

## 조회 도구

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

다음 파일은 `.gitignore`로 제외됩니다.

```text
.env
.venv/
data/kis_token*.json
data/signals.db
logs/
__pycache__/
.pytest_cache/
```

공개 저장소에 올리기 전 항상 실행하세요.

```powershell
python -m app.tools.security_check
git add --dry-run .
```
