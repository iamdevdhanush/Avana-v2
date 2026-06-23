import math

TITLE_DUP_THRESHOLD = 0.6
TITLE_PROXIMITY_THRESHOLD = 0.3
PROXIMITY_DEG_THRESHOLD = 0.1


def title_similarity(t1: str, t2: str) -> float:
    if not t1 or not t2:
        return 0.0
    w1 = set(t1.lower().split())
    w2 = set(t2.lower().split())
    if not w1 or not w2:
        return 0.0
    return len(w1 & w2) / len(w1 | w2)


def is_duplicate_by_title_and_proximity(
    candidate_title: str,
    existing_title: str,
    candidate_lat: float | None,
    candidate_lng: float | None,
    existing_lat: float,
    existing_lng: float,
) -> bool:
    sim = title_similarity(candidate_title, existing_title)
    if sim >= TITLE_DUP_THRESHOLD:
        return True
    if sim >= TITLE_PROXIMITY_THRESHOLD and candidate_lat is not None and candidate_lng is not None:
        dist = math.sqrt(
            (candidate_lat - existing_lat) ** 2
            + (candidate_lng - existing_lng) ** 2
        )
        if dist < PROXIMITY_DEG_THRESHOLD:
            return True
    return False
