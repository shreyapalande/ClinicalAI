import math
from services.gemini import embed_text


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def semantic_search(query: str, visits: list, top_k: int = 10) -> list:
    """
    visits: list of Visit ORM objects that have a non-null embedding.
    Returns list of (visit, score) sorted by descending similarity.
    """
    query_vec = embed_text(query)
    scored = []
    for visit in visits:
        if visit.embedding:
            score = cosine_similarity(query_vec, visit.embedding)
            scored.append((visit, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]
