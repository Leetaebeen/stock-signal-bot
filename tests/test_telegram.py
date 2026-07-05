import httpx

from app.alerts.telegram import TelegramAlerter


def test_telegram_send_posts_message():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True})

    alerter = TelegramAlerter(
        enabled=True,
        bot_token="token",
        chat_id="1234",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert alerter.send("hello") is True
    assert requests[0].url.path == "/bottoken/sendMessage"


def test_telegram_send_skips_when_disabled():
    alerter = TelegramAlerter(enabled=False, bot_token=None, chat_id=None)

    assert alerter.send("hello") is False
