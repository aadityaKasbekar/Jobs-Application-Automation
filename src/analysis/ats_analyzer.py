import json

from src.llm.base import LLMClient
from src.prompts import ATS_ANALYZER_SYSTEM, ATS_ANALYZER_USER


def analyze(resume_json: dict, job_row: dict, llm_client: LLMClient) -> dict:
    """
    Part 1: Run ATS analysis for a single job row.
    Returns a flat dict ready to be written as CSV columns.
    """
    user_msg = ATS_ANALYZER_USER.format(
        resume_json=json.dumps(resume_json, indent=2),
        title=job_row.get("__title", job_row.get("title", "")),
        company=job_row.get("__company", job_row.get("companyName", "")),
        location=job_row.get("__location", job_row.get("normalizedLocation", "")),
        job_description_full=job_row.get("job_description_full", ""),
    )

    result = llm_client.complete_json(ATS_ANALYZER_SYSTEM, user_msg)

    return {
        "ats_overall_score": result.get("overall_ats_score", ""),
        "ats_keyword_match_pct": result.get("keyword_match_pct", ""),
        "ats_total_jd_keywords_extracted": result.get("total_jd_keywords_extracted", ""),
        "ats_matched_jd_keywords": result.get("matched_jd_keywords", ""),
        "ats_required_skills_matched": result.get("required_skills_matched", []),
        "ats_required_skills_missing": result.get("required_skills_missing", []),
        "ats_preferred_skills_matched": result.get("preferred_skills_matched", []),
        "ats_preferred_skills_missing": result.get("preferred_skills_missing", []),
        "ats_experience_level_match": result.get("experience_level_match", {}),
        "ats_education_match": result.get("education_match", {}),
        "ats_title_alignment_score": result.get("title_alignment_score", ""),
        "ats_top_keywords_missing": result.get("top_keywords_missing", []),
        "ats_fit_summary": result.get("fit_summary", ""),
        "_raw_ats": result,  # kept for passing to Part 2, not written to CSV
    }
