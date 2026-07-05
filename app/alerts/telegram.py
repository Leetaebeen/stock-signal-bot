import httpx


class TelegramAlerter:
    def __init__(
        self,
        enabled: bool,
        bot_token: str | None,
        chat_id: str | None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.enabled = enabled
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.http_client = http_client or httpx.Client(timeout=10)

    def send(self, message: str) -> bool:
        if not self.enabled:
            return False
        if not self.bot_token or not self.chat_id:
            raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required.")

        response = self.http_client.post(
            f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
            json={
                "chat_id": self.chat_id,
                "text": message,
                "disable_web_page_preview": True,
            },
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Telegram send failed: {response.status_code} {response.text}")
        payload = response.json()
        return bool(payload.get("ok"))
