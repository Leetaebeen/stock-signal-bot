import httpx


class TelegramAlerter:
    def __init__(self, enabled: bool, bot_token: str | None, chat_id: str | None) -> None:
        self.enabled = enabled
        self.bot_token = bot_token
        self.chat_id = chat_id

    async def send(self, message: str) -> bool:
        if not self.enabled or not self.bot_token or not self.chat_id:
            return False
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json={"chat_id": self.chat_id, "text": message})
            response.raise_for_status()
        return True
