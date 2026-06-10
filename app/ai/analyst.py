import json
from dataclasses import replace
from typing import Any

import httpx

from app.config import Settings
from app.models import AIAnalysis, SignalCandidate
from app.signals.trade_plan import build_trade_plan

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
GEMINI_GENERATE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-lite"


async def analyze_candidate(candidate: SignalCandidate, settings: Settings) -> SignalCandidate:
    if not settings.ai_analysis_enabled:
        return candidate

    provider = settings.ai_provider.lower()
    if not settings.ai_api_key:
        raise RuntimeError("AI_API_KEY is required when AI_ANALYSIS_ENABLED=true.")

    if provider == "anthropic":
        if not settings.ai_model:
            raise RuntimeError("AI_MODEL is required when AI_PROVIDER=anthropic.")
        client = AnthropicAnalyst(
            api_key=settings.ai_api_key,
            model=settings.ai_model,
            timeout_seconds=settings.ai_timeout_seconds,
        )
    elif provider == "gemini":
        client = GeminiAnalyst(
            api_key=settings.ai_api_key,
            model=settings.ai_model or DEFAULT_GEMINI_MODEL,
            timeout_seconds=settings.ai_timeout_seconds,
        )
    else:
        raise RuntimeError(f"Unsupported AI_PROVIDER={settings.ai_provider}. Use gemini or anthropic.")

    analysis = await client.analyze(candidate)
    return replace(candidate, ai_analysis=analysis)


def ai_allows_alert(candidate: SignalCandidate, min_confidence: int) -> bool:
    analysis = candidate.ai_analysis
    if analysis is None:
        return True
    return analysis.recommendation == "BUY" and analysis.confidence >= min_confidence


class AnthropicAnalyst:
    def __init__(self, api_key: str, model: str, timeout_seconds: float = 20.0) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def analyze(self, candidate: SignalCandidate) -> AIAnalysis:
        prompt = _build_prompt(candidate)
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                ANTHROPIC_MESSAGES_URL,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": ANTHROPIC_VERSION,
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 700,
                    "temperature": 0.1,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
        if response.status_code >= 400:
            raise RuntimeError(f"AI analysis request failed: {response.status_code} {response.text}")

        text = _extract_anthropic_text(response.json())
        return parse_ai_analysis(text)


class GeminiAnalyst:
    def __init__(self, api_key: str, model: str = DEFAULT_GEMINI_MODEL, timeout_seconds: float = 20.0) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = max(timeout_seconds, 60.0)

    async def analyze(self, candidate: SignalCandidate) -> AIAnalysis:
        prompt = _build_prompt(candidate)
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                GEMINI_GENERATE_URL.format(model=self.model),
                headers={
                    "x-goog-api-key": self.api_key,
                    "content-type": "application/json",
                },
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.1,
                        "maxOutputTokens": 1200,
                        "responseMimeType": "application/json",
                        "responseSchema": _gemini_response_schema(),
                        "thinkingConfig": {"thinkingBudget": 0},
                    },
                },
            )
        if response.status_code >= 400:
            raise RuntimeError(f"AI analysis request failed: {response.status_code} {response.text}")

        text = extract_gemini_text(response.json())
        return parse_ai_analysis(text)


def parse_ai_analysis(text: str) -> AIAnalysis:
    payload = _load_json_object(text)
    recommendation = str(payload.get("recommendation") or "").upper()
    if recommendation not in {"BUY", "WATCH", "SKIP"}:
        recommendation = "SKIP"

    confidence = _to_int(payload.get("confidence"), default=0)
    confidence = min(100, max(0, confidence))
    summary = _clean_text(payload.get("summary"), default="AI 분석 요약 없음")
    key_points = _clean_list(payload.get("key_points"))[:5]
    risk_notes = _clean_list(payload.get("risk_notes"))[:5]

    return AIAnalysis(
        recommendation=recommendation,  # type: ignore[arg-type]
        confidence=confidence,
        summary=summary,
        key_points=key_points,
        risk_notes=risk_notes,
    )


def extract_gemini_text(payload: dict[str, Any]) -> str:
    parts = []
    for candidate in payload.get("candidates") or []:
        content = candidate.get("content") if isinstance(candidate, dict) else None
        for part in (content or {}).get("parts") or []:
            if isinstance(part, dict) and part.get("text"):
                parts.append(str(part["text"]))
    return "\n".join(parts).strip()


def _build_prompt(candidate: SignalCandidate) -> str:
    snap = candidate.snapshot
    plan = build_trade_plan(candidate)
    payload = {
        "market": snap.market,
        "symbol": snap.symbol,
        "name": snap.name,
        "price": snap.price,
        "change_pct": snap.change_pct,
        "volume_ratio": snap.volume_ratio,
        "trading_value_krw": snap.trading_value_krw,
        "open_price": snap.open_price,
        "high_price": snap.high_price,
        "low_price": snap.low_price,
        "vwap_price": snap.vwap_price,
        "vi_gap_pct": snap.vi_gap_pct,
        "foreign_flow_score": snap.foreign_flow_score,
        "institution_flow_score": snap.institution_flow_score,
        "program_flow_score": snap.program_flow_score,
        "news_score": snap.news_score,
        "disclosure_risk": snap.disclosure_risk,
        "rule_score": candidate.score,
        "rule_reasons": candidate.reasons,
        "rule_risks": candidate.risks,
        "trade_plan": plan.to_dict(),
    }
    return (
        "너는 개인 단타 알림용 리스크 검토 AI다. "
        "아래 실시간 후보 데이터만 근거로 최종 알림 여부를 판단해라. "
        "새로운 가격, 뉴스, 재무정보를 상상하지 마라. "
        "매매 보장은 하지 말고, 데이터가 부족하거나 추격 위험이 크면 WATCH 또는 SKIP을 선택해라.\n\n"
        "출력은 설명 없이 JSON 객체 하나만 반환해라.\n"
        "형식:\n"
        "{"
        "\"recommendation\":\"BUY|WATCH|SKIP\","
        "\"confidence\":0,"
        "\"summary\":\"한 문장 요약\","
        "\"key_points\":[\"근거1\",\"근거2\"],"
        "\"risk_notes\":[\"리스크1\",\"리스크2\"]"
        "}\n\n"
        f"후보 데이터:\n{json.dumps(payload, ensure_ascii=False)}"
    )


def _gemini_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "recommendation": {
                "type": "string",
                "enum": ["BUY", "WATCH", "SKIP"],
            },
            "confidence": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
            },
            "summary": {
                "type": "string",
            },
            "key_points": {
                "type": "array",
                "items": {"type": "string"},
            },
            "risk_notes": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["recommendation", "confidence", "summary", "key_points", "risk_notes"],
    }


def _extract_anthropic_text(payload: dict[str, Any]) -> str:
    parts = []
    for item in payload.get("content") or []:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(str(item.get("text") or ""))
    return "\n".join(parts).strip()


def _load_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise RuntimeError(f"AI analysis did not return JSON: {text[:200]}")
    return json.loads(cleaned[start : end + 1])


def _clean_text(value: Any, default: str) -> str:
    text = str(value or "").strip()
    return text if text else default


def _clean_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
