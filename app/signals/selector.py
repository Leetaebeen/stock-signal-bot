from app.models import SignalCandidate


def select_strongest(candidates: list[SignalCandidate], min_score: int) -> SignalCandidate | None:
    valid = [candidate for candidate in candidates if candidate.score >= min_score]
    if not valid:
        return None
    return sorted(valid, key=lambda item: item.score, reverse=True)[0]
