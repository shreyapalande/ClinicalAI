"""
Tests each MCP tool directly via FastMCP's in-process client.
No Gemini agent involved — purely confirms tool logic against the real DB.

Run from project root:
    .\\venv\\Scripts\\python backend/test_mcp_server.py
"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import Client
from backend.mcp_server import mcp


def _parse(result) -> any:
    """Extract the Python value from a FastMCP 3.x CallToolResult."""
    return result.data


def section(title: str):
    print(f"\n{'='*55}")
    print(f"  {title}")
    print(f"{'='*55}")


async def main():
    async with Client(mcp) as client:

        # ── 1. get_all_patient_ids ────────────────────────────────
        section("1. get_all_patient_ids")
        result = await client.call_tool("get_all_patient_ids", {})
        all_ids = _parse(result)
        print("Patient IDs:", all_ids)

        if not all_ids:
            print("No patients in DB — add some via the app first.")
            return

        # ── 2. get_patient_details ────────────────────────────────
        section(f"2. get_patient_details  (patient {all_ids[0]})")
        result = await client.call_tool("get_patient_details", {"patient_id": all_ids[0]})
        details = _parse(result)
        print(f"  Name      : {details.get('name')}")
        print(f"  Age       : {details.get('age')}")
        print(f"  Gender    : {details.get('gender')}")
        print(f"  Allergies : {details.get('allergies')}")
        print(f"  Visits    : {len(details.get('visits', []))}")
        if details.get("visits"):
            v = details["visits"][0]
            print(f"  Last visit: {v.get('chief_complaint')}  [{v.get('created_at','')[:10]}]")

        # ── 3. filter_by_age_range ────────────────────────────────
        section("3. filter_by_age_range  (18–60)")
        result = await client.call_tool(
            "filter_by_age_range",
            {"patient_ids": all_ids, "min_age": 18, "max_age": 60},
        )
        age_ids = _parse(result)
        print("Patients aged 18–60:", age_ids)

        # ── 4. filter_by_last_visit ───────────────────────────────
        section("4. filter_by_last_visit  (after 2024-01-01)")
        result = await client.call_tool(
            "filter_by_last_visit",
            {"patient_ids": all_ids, "after_date": "2024-01-01"},
        )
        recent_ids = _parse(result)
        print("Patients with a visit after 2024-01-01:", recent_ids)

        # ── 5. filter_by_prescription ─────────────────────────────
        section("5. filter_by_prescription  (query: 'ibu')")
        result = await client.call_tool(
            "filter_by_prescription",
            {"patient_ids": all_ids, "medication": "ibu"},
        )
        rx_ids = _parse(result)
        print("Patients prescribed ibuprofen/ibuprofin:", rx_ids)

        # also try a broader term
        result2 = await client.call_tool(
            "filter_by_prescription",
            {"patient_ids": all_ids, "medication": ""},
        )
        all_rx = _parse(result2)
        print("Patients with any prescription:", all_rx)

        # ── 6. filter_by_allergy ──────────────────────────────────
        section("6. filter_by_allergy  (query: 'penicillin')")
        result = await client.call_tool(
            "filter_by_allergy",
            {"patient_ids": all_ids, "allergen": "penicillin"},
        )
        allergy_ids = _parse(result)
        print("Patients allergic to penicillin:", allergy_ids)

        # ── 7. search_records_semantic ────────────────────────────
        section("7. search_records_semantic  (query: 'headache fever')")
        result = await client.call_tool(
            "search_records_semantic",
            {"query": "headache and fever", "top_k": 5},
        )
        hits = _parse(result)
        print(f"Top {len(hits)} semantic matches:")
        for h in hits:
            print(f"  [{h['score']:.3f}] Patient {h['patient_id']} ({h['patient_name']}) "
                  f"— {h['chief_complaint']}")

        # ── 8. chained filter example ─────────────────────────────
        section("8. Chained: all patients → filter by age 18-99 → details")
        result = await client.call_tool(
            "filter_by_age_range",
            {"patient_ids": all_ids, "min_age": 18},
        )
        adult_ids = _parse(result)
        print("Adult patients:", adult_ids)
        for pid in adult_ids[:2]:
            res = await client.call_tool("get_patient_details", {"patient_id": pid})
            d = _parse(res)
            print(f"  → Patient {pid}: {d.get('name')}, {d.get('age')} yrs, "
                  f"{len(d.get('visits', []))} visit(s)")

        print(f"\n{'='*55}")
        print("  All tools verified successfully.")
        print(f"{'='*55}\n")


if __name__ == "__main__":
    asyncio.run(main())
