from fastapi import APIRouter, Query
from backend.tools import search_records_semantic

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("/")
def search(
    q: str = Query(..., min_length=1),
    top_k: int = Query(default=10, le=50),
):
    results = search_records_semantic(q, top_k=top_k)
    return {"query": q, "results": results}
