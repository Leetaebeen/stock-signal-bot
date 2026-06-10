from app.models import MarketSnapshot


async def scan_us_market(client) -> list[MarketSnapshot]:
    return await client.get_us_snapshots()
