"""
Agent endpoint: Gemini with function calling over the 7 MCP tools.
POST /api/agent/query  →  {answer: str, patients: list[dict]}
"""

import os
from fastapi import APIRouter, Body, HTTPException
from google import genai
from google.genai import types
from dotenv import load_dotenv

from backend.tools import (
    get_all_patient_ids,
    search_records_semantic,
    get_patient_details,
    filter_by_last_visit,
    filter_by_prescription,
    filter_by_age_range,
    filter_by_allergy,
)

load_dotenv(override=True)

router = APIRouter(prefix="/api/agent", tags=["agent"])
_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
FLASH_MODEL = "gemini-2.5-flash"

TOOL_MAP = {
    "get_all_patient_ids": get_all_patient_ids,
    "search_records_semantic": search_records_semantic,
    "get_patient_details": get_patient_details,
    "filter_by_last_visit": filter_by_last_visit,
    "filter_by_prescription": filter_by_prescription,
    "filter_by_age_range": filter_by_age_range,
    "filter_by_allergy": filter_by_allergy,
}

_int_list = {"type": "array", "items": {"type": "integer"}}

TOOLS = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="get_all_patient_ids",
            description=(
                "Returns the IDs of every patient in the database. "
                "Use as the entry point for population-wide queries, "
                "then pass the list into filter_by_* tools to narrow down."
            ),
            parameters={"type": "object", "properties": {}},
        ),
        types.FunctionDeclaration(
            name="search_records_semantic",
            description=(
                "Searches all visit records by meaning (not keywords). "
                "Searching 'chest pain' also matches 'angina' or 'cardiac discomfort'. "
                "Use for open-ended clinical queries. Returns up to top_k visits "
                "with patient_id, patient_name, score, chief_complaint, symptoms, diagnoses, prescriptions."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural-language description of what to find"},
                    "top_k": {"type": "integer", "description": "Maximum results to return (default 10)"},
                },
                "required": ["query"],
            },
        ),
        types.FunctionDeclaration(
            name="get_patient_details",
            description=(
                "Returns the complete medical record for one patient: demographics and full visit history. "
                "Call this after identifying a patient to retrieve details before answering about them."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "patient_id": {"type": "integer", "description": "The numeric patient ID"},
                },
                "required": ["patient_id"],
            },
        ),
        types.FunctionDeclaration(
            name="filter_by_last_visit",
            description=(
                "Filters patients by the date of their most recent visit. "
                "Use for queries like 'patients seen in the last 3 months' or 'not visited since 2024'. "
                "Dates must be ISO format YYYY-MM-DD. Returns subset of patient_ids."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "patient_ids": _int_list,
                    "before_date": {"type": "string", "description": "Keep patients whose last visit was BEFORE this date (YYYY-MM-DD)"},
                    "after_date": {"type": "string", "description": "Keep patients whose last visit was AFTER this date (YYYY-MM-DD)"},
                },
                "required": ["patient_ids"],
            },
        ),
        types.FunctionDeclaration(
            name="filter_by_prescription",
            description=(
                "Filters patients who have been prescribed a specific medication (partial, case-insensitive match). "
                "'amox' matches 'Amoxicillin'. Searches all visits. Returns subset of patient_ids."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "patient_ids": _int_list,
                    "medication": {"type": "string", "description": "Drug name or partial name"},
                },
                "required": ["patient_ids", "medication"],
            },
        ),
        types.FunctionDeclaration(
            name="filter_by_age_range",
            description=(
                "Filters patients by age. Use for 'elderly patients over 65', 'adults 40-60', etc. "
                "Patients with no recorded age are excluded. Returns subset of patient_ids."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "patient_ids": _int_list,
                    "min_age": {"type": "integer", "description": "Minimum age inclusive"},
                    "max_age": {"type": "integer", "description": "Maximum age inclusive"},
                },
                "required": ["patient_ids"],
            },
        ),
        types.FunctionDeclaration(
            name="filter_by_allergy",
            description=(
                "Filters patients with a recorded allergy (partial, case-insensitive match). "
                "Critical for safe prescribing. 'sulfa' matches 'Sulfamethoxazole'. Returns subset of patient_ids."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "patient_ids": _int_list,
                    "allergen": {"type": "string", "description": "Allergen name or partial name"},
                },
                "required": ["patient_ids", "allergen"],
            },
        ),
    ]
)

SYSTEM_PROMPT = """\
You are a clinical AI assistant that answers questions about patient records.
You have tools to query a medical database.

Strategy:
- For broad queries, call get_all_patient_ids() then apply filter_by_* tools to narrow down.
- For clinical/symptom queries, use search_records_semantic() first.
- Always finish with get_patient_details() for patients you will specifically discuss.
- Chain filters for complex queries: age → prescription → allergy, etc.

Answer clearly and concisely. Name patients and cite medical facts.
If no patients match, say so directly.

User query: """


@router.post("/query")
def agent_query(body: dict = Body(...)):
    query = body.get("query", "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query required")

    found_patient_ids: set[int] = set()
    contents: list = [
        types.Content(role="user", parts=[types.Part(text=SYSTEM_PROMPT + query)])
    ]
    final_answer = "I could not find relevant information for your query."

    for _ in range(12):
        response = _client.models.generate_content(
            model=FLASH_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                tools=[TOOLS],
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )

        model_content = response.candidates[0].content
        contents.append(model_content)

        fn_calls = [
            p.function_call
            for p in model_content.parts
            if getattr(p, "function_call", None)
        ]

        if not fn_calls:
            for part in model_content.parts:
                if getattr(part, "text", None):
                    final_answer = part.text
                    break
            break

        fn_response_parts = []
        for fc in fn_calls:
            fn_name = fc.name
            fn_args = dict(fc.args) if fc.args else {}

            try:
                result = TOOL_MAP[fn_name](**fn_args)
            except Exception as exc:
                result = {"error": str(exc)}

            # Collect patient IDs from tool results
            if fn_name == "search_records_semantic" and isinstance(result, list):
                found_patient_ids.update(r["patient_id"] for r in result)
            elif fn_name == "get_patient_details" and isinstance(result, dict) and "id" in result:
                found_patient_ids.add(result["id"])
            elif fn_name.startswith("filter_by_") and isinstance(result, list):
                found_patient_ids.update(result)

            fn_response_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=fn_name,
                        response={"result": result},
                    )
                )
            )

        contents.append(types.Content(role="user", parts=fn_response_parts))

    # Fetch full details for all found patients
    patients = []
    for pid in sorted(found_patient_ids):
        details = get_patient_details(pid)
        if "error" not in details:
            patients.append(details)

    return {"answer": final_answer, "patients": patients}
