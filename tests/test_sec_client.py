import httpx

from app.disclosures.sec_client import SecClient, evaluate_sec_risk


def test_sec_client_disabled_for_example_user_agent():
    client = SecClient("stock-signal-bot/0.1 your-email@example.com")

    assert not client.enabled
    assert client.recent_filings("NVDA") == []
    assert client.risk_score("NVDA") == 0.0
    assert client.last_status == "disabled"


def test_sec_client_disabled_for_placeholder_domain_user_agent():
    client = SecClient("stock-signal-bot/0.1 your-email@domain.com")

    assert not client.enabled


def test_evaluate_sec_risk_detects_offering_forms():
    risk = evaluate_sec_risk(
        [
            {"form": "S-3", "primaryDocDescription": "Registration statement"},
            {"form": "8-K", "primaryDocDescription": "Current report"},
        ]
    )

    assert risk == 8.0


def test_sec_client_reads_recent_filings():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "www.sec.gov":
            return httpx.Response(
                200,
                json={
                    "0": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"},
                },
            )
        if request.url.host == "data.sec.gov":
            return httpx.Response(
                200,
                json={
                    "filings": {
                        "recent": {
                            "accessionNumber": ["0000000000-26-000001"],
                            "filingDate": ["2026-06-10"],
                            "form": ["S-3"],
                            "primaryDocument": ["s-3.htm"],
                            "primaryDocDescription": ["Registration statement"],
                        }
                    }
                },
            )
        return httpx.Response(404)

    client = SecClient("stock-signal-bot/0.1 test@example.org", http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    filings = client.recent_filings("NVDA", days=30)

    assert client.lookup_cik("NVDA") == "0001045810"
    assert filings[0]["form"] == "S-3"
    assert evaluate_sec_risk(filings) == 8.0
    assert client.last_status == "ok"


def test_sec_client_treats_forbidden_submission_as_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403)

    client = SecClient("stock-signal-bot/0.1 test@example.org", http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    assert client.recent_filings("NVDA", days=30) == []
    assert client.last_status == "blocked_403"
