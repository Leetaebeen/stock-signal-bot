import logging

import httpx

logger = logging.getLogger(__name__)


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
            try:
                response = await client.post(url, json={"chat_id": self.chat_id, "text": message})
            except httpx.HTTPError as exc:
                logger.warning("telegram send failed transport_error=%s", exc.__class__.__name__)
                return False

        if response.status_code >= 400:
            logger.warning(
                "telegram send failed status_code=%s description=%s",
                response.status_code,
                _telegram_error_description(response),
            )
            return False
        return True


def _telegram_error_description(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return "unavailable"
    description = payload.get("description")
    if not isinstance(description, str):
        return "unavailable"
    return description[:200]
