# 배포 메모

현재 버전은 KIS 모의투자 자동매매 검증 단계입니다. 실계좌 주문은 차단합니다.

서버 배포 전 확인:

```bash
python -m pytest -q
python -m app.tools.security_check
python -m app.tools.kis_auth_check
python -m app.tools.kis_balance_check
```

`.env`, 토큰 캐시, SQLite DB, 로그 파일은 Git에 올리지 않습니다.
