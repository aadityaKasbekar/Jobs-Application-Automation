import json

from src.llm.base import LLMClient
from src.prompts import IMPROVER_SYSTEM, IMPROVER_USER


def improve(resume_json: dict, job_row: dict, ats_results: dict, llm_client: LLMClient) -> dict:
    """
    Part 2: Generate improvement suggestions for a single job row.
    Receives ATS results from Part 1 as additional context.
    Returns a flat dict ready to be written as CSV columns.
    """
    raw_ats = ats_results.get("_raw_ats", {k: v for k, v in ats_results.items() if not k.startswith("_")})

    user_msg = IMPROVER_USER.format(
        resume_json=json.dumps(resume_json, indent=2),
        title=job_row.get("__title", job_row.get("title", "")),
        company=job_row.get("__company", job_row.get("companyName", "")),
        job_description_full=job_row.get("job_description_full", ""),
        ats_results_json=json.dumps(raw_ats, indent=2),
    )

    result = llm_client.complete_json(IMPROVER_SYSTEM, user_msg)

    return {
        "improve_skills_to_add": result.get("skills_to_add", []),
        "improve_skills_to_emphasize": result.get("skills_to_emphasize", []),
        "improve_experience_bullets": result.get("experience_bullets_to_improve", []),
        "improve_resume_edit_prompt": result.get("resume_edit_prompt", ""),
        "improve_overall_strategy": result.get("overall_strategy", ""),
    }
