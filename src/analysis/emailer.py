import json

from src.llm.base import LLMClient
from src.prompts import EMAIL_GENERATOR_SYSTEM, EMAIL_GENERATOR_USER


def generate_email(resume_json: dict, job_row: dict, llm_client: LLMClient) -> dict:
    """
    Part 3: Generate a cold email for a single job row.
    Uses ONLY resume_json and job_row — does NOT receive improvement suggestions.
    Returns a flat dict ready to be written as CSV columns.
    """
    user_msg = EMAIL_GENERATOR_USER.format(
        resume_json=json.dumps(resume_json, indent=2),
        title=job_row.get("__title", job_row.get("title", "")),
        company=job_row.get("__company", job_row.get("companyName", "")),
        location=job_row.get("__location", job_row.get("normalizedLocation", "")),
        job_description_full=job_row.get("job_description_full", ""),
    )

    result = llm_client.complete_json(EMAIL_GENERATOR_SYSTEM, user_msg)

    return {
        "email_subject": result.get("subject", ""),
        "email_body": result.get("body", ""),
    }
