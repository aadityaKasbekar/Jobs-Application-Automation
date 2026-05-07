# Job Application Automation — Plan

## Overview

A Python CLI tool that reads a CSV of job postings, parses a resume PDF, and uses an LLM (Claude / OpenAI / Gemini — pluggable) to produce three outputs per job row:

1. **Part 1 — ATS Metrics**: How well does the resume match this job?
2. **Part 2 — Improvement Suggestions**: What to change in the resume for this role?
3. **Part 3 — Cold Email**: A ready-to-send email (subject + body) to a recruiter or hiring manager.

All outputs are appended as new columns to the preprocessed input CSV. No database. No duplicate files beyond what is strictly necessary.

---

## Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| CLI | Click |
| PDF Parsing | pdfplumber |
| Data | pandas |
| LLM: Claude | anthropic SDK |
| LLM: OpenAI | openai SDK |
| LLM: Gemini | google-generativeai SDK |
| Config | PyYAML |
| Env vars | python-dotenv |
| Terminal UI | rich |

**Future FastAPI expansion**: All business logic lives in pure service functions with no CLI dependencies. Adding FastAPI later means writing route handlers that call the same functions.

---

## Directory Structure

```
jobs_application_automation/
├── plan.md                        ← this file
├── prompts.md                     ← all LLM system prompts + rationale
├── config.yaml                    ← column mapping, model defaults, batch settings
├── .env.example                   ← API key template
├── .gitignore
├── requirements.txt
├── main.py                        ← CLI entry point (click)
│
├── src/
│   ├── __init__.py
│   ├── processor.py               ← batch orchestrator + checkpoint manager
│   ├── prompts.py                 ← all system prompt strings (single source of truth)
│   │
│   ├── resume/
│   │   ├── __init__.py
│   │   ├── parser.py              ← PDF text extraction → LLM → structured JSON
│   │   └── cache.py               ← SHA256-based change detection + JSON cache
│   │
│   ├── csv/
│   │   ├── __init__.py
│   │   ├── preprocessor.py        ← raw CSV → normalized llm_input CSV
│   │   └── writer.py              ← append result columns to DataFrame
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py                ← abstract LLMClient
│   │   ├── claude_client.py
│   │   ├── openai_client.py
│   │   ├── gemini_client.py
│   │   └── factory.py             ← create_client(provider, api_key, model)
│   │
│   └── analysis/
│       ├── __init__.py
│       ├── ats_analyzer.py        ← Part 1
│       ├── improver.py            ← Part 2
│       └── emailer.py             ← Part 3
│
└── data/
    ├── resume/                    ← place resume.pdf here
    └── checkpoints/               ← auto-generated .json checkpoint files
```

---

## Data Flow

```
resume.pdf
    │
    ▼
[resume/cache.py]
  SHA256(pdf) == cached_hash?
    YES → load resume_cache.json
    NO  → pdfplumber extract text → LLM → structured JSON → save resume_cache.json
    │
    ▼
resume_json (dict, single source of truth for this run)

raw_jobs.csv
    │
    ▼
[csv/preprocessor.py]
  apply column_mapping from config.yaml
  merge description_columns → job_description_full
  save → llm_input_<original_filename>.csv
    │
    ▼
llm_input csv (canonical columns + all original columns retained)
    │
    ▼
[processor.py — BatchProcessor]
  load checkpoint (skip already-processed rows)
  for each unprocessed row in batches of 10:
      │
      ├── Part 1: ats_analyzer.analyze(resume_json, job_row, llm_client) → ats_dict
      ├── Part 2: improver.improve(resume_json, job_row, ats_dict, llm_client) → improve_dict
      └── Part 3: emailer.generate_email(resume_json, job_row, llm_client) → email_dict
      │
      write results to DataFrame row
      save DataFrame → CSV after each row
      save checkpoint JSON after every 10 rows
    │
    ▼
llm_input csv (original cols + ats_* + improve_* + email_* + meta_* columns)
```

---

## Resume Change Detection

**File**: `src/resume/cache.py`

Cache format (`data/resume_cache.json`):
```json
{
  "pdf_hash": "sha256hexstring",
  "parsed_at": "2026-05-06T12:00:00",
  "resume_json": { ... }
}
```

Logic on every run:
1. Compute SHA256 of raw PDF bytes
2. Load `data/resume_cache.json` if it exists
3. If `pdf_hash` matches → return cached `resume_json` (no LLM call)
4. If `pdf_hash` differs or no cache → extract text via pdfplumber → LLM structured parse → save new cache
5. Rich-print a delta summary showing which top-level sections changed (skills, experience, education, etc.)

Only one `resume_cache.json` ever exists. The system never creates a second one.

---

## CSV Preprocessing

**File**: `src/csv/preprocessor.py`

Two jobs:
1. **Column mapping**: `config.yaml` defines `canonical_name → raw_column_name`. Any CSV with a different schema just needs a different mapping block — the rest of the pipeline stays the same.
2. **JD consolidation**: Multiple description columns (e.g. `shortDescription`, `basicQualifications`, `preferredQualifications`, `description`) are concatenated in order with section headers into a single `job_description_full` column.

Output: `llm_input_<original_filename>.csv` — same directory as input. All original columns are retained; canonical columns are added alongside.

---

## LLM Client Architecture

**Files**: `src/llm/`

```python
class LLMClient(ABC):
    def complete(self, system: str, user: str) -> str: ...
    def complete_json(self, system: str, user: str) -> dict: ...
```

Three concrete implementations: `ClaudeClient`, `OpenAIClient`, `GeminiClient`.

`factory.py` maps provider name → class → instantiation. Default models in `config.yaml`; overridable via CLI.

CLI prompts at runtime:
```
Which LLM? [claude/openai/gemini]: claude
API key (or Enter to use .env): 
Model override (Enter for default claude-sonnet-4-6):
```

---

## Three LLM Calls Per Row

Each call is stateless — context is passed explicitly, not via chat session. This makes each call independently retryable and debuggable.

| Call | Inputs | System Prompt | Output |
|---|---|---|---|
| Part 1 ATS | resume_json + job_description_full | ATS Analyzer | JSON metrics |
| Part 2 Improve | resume_json + job_description_full + ats_results | Improvement Advisor | JSON suggestions |
| Part 3 Email | resume_json + job_description_full | Cold Email Generator | JSON {subject, body} |

**Part 3 constraint**: The cold email is based ONLY on the current resume JSON. It does NOT receive improvement suggestions as input — enforced structurally, not by prompt instruction alone.

---

## Output Columns Appended to CSV

### Part 1 — ATS Metrics (`ats_*`)
| Column | Type | Description |
|---|---|---|
| `ats_overall_score` | int 0–100 | Weighted composite score |
| `ats_keyword_match_pct` | int 0–100 | % of JD keywords found in resume |
| `ats_required_skills_matched` | JSON list | Required skills present in resume |
| `ats_required_skills_missing` | JSON list | Required skills absent from resume |
| `ats_preferred_skills_matched` | JSON list | Preferred skills present |
| `ats_preferred_skills_missing` | JSON list | Preferred skills absent |
| `ats_experience_level_match` | JSON dict | {jd_requires, candidate_has, matches, explanation} |
| `ats_education_match` | JSON dict | {jd_requires, candidate_has, matches, explanation} |
| `ats_title_alignment_score` | int 0–100 | Semantic closeness of past titles to target role |
| `ats_top_keywords_missing` | JSON list | Top 10 impactful missing keywords |
| `ats_fit_summary` | text | 2–3 sentence honest assessment |

### Part 2 — Improvement Suggestions (`improve_*`)
| Column | Type | Description |
|---|---|---|
| `improve_skills_to_add` | JSON list | [{skill, reason, how_to_acquire, estimated_ats_impact}] |
| `improve_skills_to_emphasize` | JSON list | [{skill, current_mention, suggested_rewrite, estimated_ats_impact}] |
| `improve_experience_bullets` | JSON list | [{current_bullet, improved_bullet, reason}] |
| `improve_resume_edit_prompt` | text | Self-contained prompt ready to paste into any LLM chat |
| `improve_overall_strategy` | text | 3–5 sentence coaching note |

### Part 3 — Cold Email (`email_*`)
| Column | Type | Description |
|---|---|---|
| `email_subject` | text | Subject line (≤60 chars) |
| `email_body` | text | Plain text body (≤180 words) |

### Processing Metadata (`meta_*`)
| Column | Type | Description |
|---|---|---|
| `meta_processed_at` | ISO timestamp | When this row was processed |
| `meta_llm_provider` | text | claude / openai / gemini |
| `meta_llm_model` | text | Exact model string used |
| `meta_processing_error` | text | Error message if any call failed, else empty |

---

## Batch Processing & Checkpoints

**Batch size**: 10 rows (configurable in `config.yaml`)  
**Checkpoint file**: `data/checkpoints/<csv_stem>_checkpoint.json`

```json
{
  "csv_path": "/path/to/llm_input_amazon_jobs_clean.csv",
  "processed_row_ids": ["10412066", "10512034", ...],
  "failed_row_ids": ["10900123"],
  "last_processed_at": "2026-05-06T14:23:00",
  "total_rows": 271,
  "completed_rows": 42
}
```

On restart:
- Checkpoint is loaded automatically if it exists for the same CSV
- Already-processed rows (including failed rows) are skipped by default
- `--retry-failed` flag re-processes failed rows

After each batch: DataFrame is saved to CSV + checkpoint is written.  
If LLM call fails for a row: error is written to `meta_processing_error`, row is marked in checkpoint as failed, processing continues.

---

## Configuration (`config.yaml`)

```yaml
processing:
  batch_size: 10
  delay_between_rows_sec: 1
  delay_between_batches_sec: 5

llm:
  default_models:
    claude: "claude-sonnet-4-6"
    openai: "gpt-4o"
    gemini: "gemini-1.5-pro"
  max_tokens: 4096

resume:
  pdf_path: "data/resume/resume.pdf"
  cache_path: "data/resume_cache.json"

csv:
  id_column: "icimsJobId"
  column_mapping:
    job_id: "icimsJobId"
    title: "title"
    company: "companyName"
    location: "normalizedLocation"
    job_level: "jobLevel"
    department: "department"
    hiring_manager_name: "hm_name"
    hiring_manager_email: "hm_email"
    recruiter_name: "recruiter_name"
    recruiter_email: "recruiter_email"
  description_columns:
    - "shortDescription"
    - "basicQualifications"
    - "preferredQualifications"
    - "description"
```

---

## Future FastAPI Expansion

The service functions in `src/analysis/` and `src/resume/` take plain Python objects and return plain dicts. To expose as REST API:

```python
# future: api/routes.py
@app.post("/analyze/{job_id}")
async def analyze_job(job_id: str, req: AnalyzeRequest):
    result = ats_analyzer.analyze(req.resume_json, req.job_row, llm_client)
    return result
```

No refactoring of core logic needed — just wrap in route handlers.
