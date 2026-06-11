from app.models import MarketSnapshot, SignalCandidate
from app.signals.filters import evaluate_candidate_filter


def select_strongest(candidates: list[SignalCandidate], min_score: int) -> SignalCandidate | None:
    valid = [candidate for candidate in candidates if candidate.score >= min_score]
    if not valid:
        return None
    return sorted(valid, key=lambda item: item.score, reverse=True)[0]


def select_top_gainer(snapshots: list[MarketSnapshot]) -> MarketSnapshot | None:
    valid = [
        snapshot
        for snapshot in snapshots
        if snapshot.market == "US" and snapshot.price > 0 and snapshot.change_pct > 0
    ]
    if not valid:
        return None
    return sorted(valid, key=lambda item: item.change_pct, reverse=True)[0]


def gainer_filter_risks(snapshot: MarketSnapshot) -> list[str]:
    decision = evaluate_candidate_filter(snapshot)
    return decision.risks
