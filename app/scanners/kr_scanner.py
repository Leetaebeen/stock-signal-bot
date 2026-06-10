from app.models import MarketSnapshot


async def scan_kr_market(client) -> list[MarketSnapshot]:
    return await client.get_kr_snapshots()
