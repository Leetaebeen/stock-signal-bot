import httpx

from app.disclosures.dart_client import DartClient, evaluate_disclosure_risk


def test_evaluate_disclosure_risk_detects_high_risk_titles():
    risk = evaluate_disclosure_risk(
        [
            {"report_nm": "주요사항보고서(유상증자결정)"},
            {"report_nm": "전환사채권발행결정"},
        ]
    )

    assert risk == 10.0


def test_evaluate_disclosure_risk_ignores_routine_ownership_reports():
    risk = evaluate_disclosure_risk(
        [
            {"report_nm": "최대주주등소유주식변동신고서"},
            {"report_nm": "임원ㆍ주요주주특정증권등소유상황보고서"},
            {"report_nm": "대규모기업집단현황공시[연1회(동일인용)]"},
            {"report_nm": "기업지배구조보고서공시"},
        ]
    )

    assert risk == 0.0


def test_evaluate_disclosure_risk_detects_major_shareholder_change():
    risk = evaluate_disclosure_risk(
        [
            {"report_nm": "최대주주 변경을 수반하는 주식담보제공 계약 체결"},
        ]
    )

    assert risk == 4.0


def test_dart_client_returns_empty_without_key():
    client = DartClient(api_key=None)

    assert client.recent_disclosures("005930") == []
    assert client.risk_score("005930") == 0.0


def test_dart_client_reads_disclosure_list():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/list.json"
        assert request.url.params["stock_code"] == "005930"
        return httpx.Response(
            200,
            json={
                "status": "000",
                "message": "정상",
                "list": [{"report_nm": "분기보고서"}],
            },
        )

    client = DartClient(api_key="dart-key", http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    assert client.recent_disclosures("005930") == [{"report_nm": "분기보고서"}]
