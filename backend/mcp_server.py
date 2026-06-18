"""
Clinical AI MCP Server
Exposes patient record tools for an LLM search agent.
All tool logic lives in backend/tools.py — this file just wraps them with FastMCP.

Typical agent workflow:
  1. get_all_patient_ids()             -> full population
  2. filter_by_*(patient_ids, ...)     -> narrow the list
  3. get_patient_details(patient_id)   -> fetch full record
  OR
  1. search_records_semantic(query)    -> find relevant visits directly
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Optional
from fastmcp import FastMCP
from backend.tools import (
    get_all_patient_ids as _get_all_patient_ids,
    search_records_semantic as _search_records_semantic,
    get_patient_details as _get_patient_details,
    filter_by_last_visit as _filter_by_last_visit,
    filter_by_prescription as _filter_by_prescription,
    filter_by_age_range as _filter_by_age_range,
    filter_by_allergy as _filter_by_allergy,
)

mcp = FastMCP("Clinical AI Search Agent")


@mcp.tool()
def get_all_patient_ids() -> list[int]:
    """
    Returns the IDs of every patient in the database.

    Use this as the entry point for population-wide queries.
    Pass the returned list into filter_by_* tools to narrow down to
    patients matching specific criteria.

    Returns:
        List of integer patient IDs.
    """
    return _get_all_patient_ids()


@mcp.tool()
def search_records_semantic(query: str, top_k: int = 10) -> list[dict]:
    """
    Searches all patient visit records using semantic (meaning-based) similarity.

    Unlike keyword search, this understands intent — searching 'chest pain'
    will also match records containing 'angina', 'cardiac discomfort', or
    'myocardial ischemia'. Useful for open-ended clinical queries.

    Args:
        query:  Natural-language description of what to find.
        top_k:  Maximum number of results to return (default 10).

    Returns:
        List of dicts sorted by descending relevance, each containing:
        patient_id, patient_name, visit_id, score (0-1), chief_complaint,
        symptoms, diagnoses, prescriptions, created_at.
    """
    return _search_records_semantic(query, top_k)


@mcp.tool()
def get_patient_details(patient_id: int) -> dict:
    """
    Returns the complete medical record for a single patient.

    Args:
        patient_id: The numeric patient ID.

    Returns:
        Dict with demographics and a 'visits' list (newest first).
        Returns {"error": "..."} if the patient is not found.
    """
    return _get_patient_details(patient_id)


@mcp.tool()
def filter_by_last_visit(
    patient_ids: list[int],
    before_date: Optional[str] = None,
    after_date: Optional[str] = None,
) -> list[int]:
    """
    Filters patients by the date of their most recent visit.

    Dates must be ISO format: YYYY-MM-DD (e.g. '2025-06-01').

    Args:
        patient_ids:  List of patient IDs to filter.
        before_date:  Retain patients whose last visit was BEFORE this date.
        after_date:   Retain patients whose last visit was AFTER this date.

    Returns:
        Subset of patient_ids satisfying the date constraint.
    """
    return _filter_by_last_visit(patient_ids, before_date, after_date)


@mcp.tool()
def filter_by_prescription(patient_ids: list[int], medication: str) -> list[int]:
    """
    Filters patients who have ever been prescribed a specific medication.

    Matching is case-insensitive and partial — 'amox' matches 'Amoxicillin'.

    Args:
        patient_ids:  List of patient IDs to filter.
        medication:   Drug name or partial name to search for.

    Returns:
        Subset of patient_ids who have been prescribed the medication.
    """
    return _filter_by_prescription(patient_ids, medication)


@mcp.tool()
def filter_by_age_range(
    patient_ids: list[int],
    min_age: Optional[int] = None,
    max_age: Optional[int] = None,
) -> list[int]:
    """
    Filters patients by age.

    Args:
        patient_ids:  List of patient IDs to filter.
        min_age:      Minimum age inclusive.
        max_age:      Maximum age inclusive.

    Returns:
        Subset of patient_ids whose age falls within the specified range.
    """
    return _filter_by_age_range(patient_ids, min_age, max_age)


@mcp.tool()
def filter_by_allergy(patient_ids: list[int], allergen: str) -> list[int]:
    """
    Filters patients who have a recorded allergy to a specific substance.

    Matching is case-insensitive and partial — 'sulfa' matches 'Sulfamethoxazole'.

    Args:
        patient_ids:  List of patient IDs to filter.
        allergen:     Allergen name or partial name.

    Returns:
        Subset of patient_ids who have the allergen recorded.
    """
    return _filter_by_allergy(patient_ids, allergen)


if __name__ == "__main__":
    mcp.run()
