import os

import pandas as pd
from rich.console import Console

console = Console()

# All output columns that will be appended — initialized empty so the schema is set upfront
OUTPUT_COLUMNS = [
    # Part 1
    "ats_overall_score",
    "ats_keyword_match_pct",
    "ats_total_jd_keywords_extracted",
    "ats_matched_jd_keywords",
    "ats_required_skills_matched",
    "ats_required_skills_missing",
    "ats_preferred_skills_matched",
    "ats_preferred_skills_missing",
    "ats_experience_level_match",
    "ats_education_match",
    "ats_title_alignment_score",
    "ats_top_keywords_missing",
    "ats_fit_summary",
    # Part 2
    "improve_skills_to_add",
    "improve_skills_to_emphasize",
    "improve_experience_bullets",
    "improve_resume_edit_prompt",
    "improve_overall_strategy",
    # Part 3
    "email_subject",
    "email_body",
    # Metadata
    "meta_processed_at",
    "meta_llm_provider",
    "meta_llm_model",
    "meta_processing_error",
]


def _build_jd_full(row: pd.Series, description_columns: list[str]) -> str:
    """Concatenate multiple description columns into a single job_description_full string."""
    section_labels = {
        "shortDescription": "Overview",
        "basicQualifications": "Basic Qualifications",
        "preferredQualifications": "Preferred Qualifications",
        "description": "Full Description",
        "responsibilities": "Responsibilities",
        "requirements": "Requirements",
        "minimumQualifications": "Minimum Qualifications",
    }
    parts = []
    for col in description_columns:
        if col in row and pd.notna(row[col]) and str(row[col]).strip():
            label = section_labels.get(col, col)
            parts.append(f"[{label}]\n{str(row[col]).strip()}")
    return "\n\n".join(parts)


def load_and_normalize(
    csv_path: str,
    column_mapping: dict[str, str],
    description_columns: list[str],
    id_column: str,
) -> pd.DataFrame:
    """
    Load raw CSV and add canonical columns alongside original ones.
    Adds job_description_full by merging description_columns.
    Pre-populates all output columns with empty strings.
    """
    df = pd.read_csv(csv_path, dtype=str).fillna("")

    console.print(f"Loaded [cyan]{len(df)}[/cyan] rows from [cyan]{csv_path}[/cyan]")
    console.print(f"Columns: {list(df.columns)}")

    # Add canonical columns
    for canonical, raw in column_mapping.items():
        if raw in df.columns:
            df[f"__{canonical}"] = df[raw]
        else:
            console.print(f"  [yellow]Warning:[/yellow] mapped column '{raw}' not found in CSV — {canonical} will be empty")
            df[f"__{canonical}"] = ""

    # Build unified job description
    df["job_description_full"] = df.apply(
        lambda row: _build_jd_full(row, description_columns), axis=1
    )

    # Pre-populate output columns with empty string so schema is fixed
    for col in OUTPUT_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    return df


def save_preprocessed(df: pd.DataFrame, input_csv_path: str) -> str:
    """Save normalized DataFrame as llm_input_<original_name>.csv in the same directory."""
    directory = os.path.dirname(os.path.abspath(input_csv_path))
    stem = os.path.splitext(os.path.basename(input_csv_path))[0]
    output_path = os.path.join(directory, f"llm_input_{stem}.csv")
    df.to_csv(output_path, index=False)
    console.print(f"[green]Preprocessed CSV saved → {output_path}[/green]")
    return output_path
