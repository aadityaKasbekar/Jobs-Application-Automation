# Session HandOff — Job Application Automation

> **How to use this file:** Read it at the start of every Claude Code session to get instant context. The owner will say "update Session_HandOff.md" at the end of a session to capture what changed.

---

## What This Project Does

A Python CLI tool that automates job application analysis and outreach. Given a CSV of job postings and a resume PDF, it calls an LLM (Claude / OpenAI / Gemini) and produces three outputs per job row:

1. **ATS Metrics** — resume match score, keyword analysis, skills gap
2. **Resume Improvements** — targeted suggestions grounded in the candidate's actual background
3. **Cold Email** — ready-to-send subject + body, generated from the *current* resume (not the hypothetical improved one)

All output is appended as new columns to the input CSV. No database. State lives in CSV + JSON checkpoint files.

---

## Current State (last updated: 2026-05-07)

| Item | Status |
|---|---|
| Active data | `data/input csv/amazon_jobs_clean.csv` — 271 Amazon job rows |
| Preprocessed CSV | `data/input csv/llm_input_amazon_jobs_clean.csv` — 68 columns |
| Rows processed | 3 / 271 (using gpt-5.1) |
| Checkpoint | `data/checkpoints/llm_input_amazon_jobs_clean_checkpoint.json` |
| Resume cache | `data/resume_cache.json` (Aaditya Kasbekar, ~1.8 yrs experience) |
| LLM last used | openai / gpt-5.1 |
| Failed rows | 0 |

---

## Project Structure

```
jobs_application_automation/
├── main.py                        ← CLI entry point (Click)
├── config.yaml                    ← Models, batch settings, column mapping
├── requirements.txt
├── .env                           ← API keys (gitignored)
├── .env.example                   ← Template
├── plan.md                        ← Architecture design doc
├── prompts.md                     ← Prompt design notes
├── Session_HandOff.md             ← This file
│
├── src/
│   ├── processor.py               ← Batch orchestrator + checkpoint manager
│   ├── prompts.py                 ← All LLM prompt strings (single source of truth)
│   ├── resume/
│   │   ├── parser.py              ← pdfplumber → raw text → LLM → JSON
│   │   └── cache.py               ← SHA256-based cache + delta detection
│   ├── csv/
│   │   ├── preprocessor.py        ← Raw CSV → normalized llm_input CSV
│   │   └── writer.py              ← Append result columns to DataFrame
│   ├── llm/
│   │   ├── base.py                ← Abstract LLMClient + JSON retry logic
│   │   ├── claude_client.py       ← Anthropic SDK wrapper
│   │   ├── openai_client.py       ← OpenAI SDK wrapper
│   │   ├── gemini_client.py       ← google-genai SDK wrapper
│   │   └── factory.py             ← create_client(provider, api_key, model, ...)
│   └── analysis/
│       ├── ats_analyzer.py        ← Part 1: ATS scoring
│       ├── improver.py            ← Part 2: Resume improvement suggestions
│       └── emailer.py             ← Part 3: Cold email generation
│
└── data/
    ├── resume/resume.pdf          ← Place resume here
    ├── resume_cache.json          ← Cached parsed resume JSON
    ├── input csv/                 ← Raw + preprocessed CSVs live here
    └── checkpoints/               ← Per-CSV checkpoint JSONs
```

---

## End-to-End Data Flow

```
python main.py
    │
    ├─ 1. Load config.yaml
    ├─ 2. Prompt: LLM provider → API key → model
    ├─ 3. RESUME: SHA256(pdf) → check cache → if miss: pdfplumber + LLM parse → cache
    ├─ 4. CSV PREPROCESS: raw CSV → apply column_mapping → merge descriptions → llm_input_*.csv
    ├─ 5. CHECKPOINT: load processed_row_ids + failed_row_ids → skip already-done rows
    │
    └─ 6. BATCH LOOP (10 rows/batch):
           FOR each unprocessed row:
               Part 1: ATS Analyzer   (resume_json + job_description_full)
               Part 2: Improver       (resume_json + job_row + ats_results)
               Part 3: Email          (resume_json + job_row only — no ats/improve input)
               Write results → save CSV → update checkpoint
               On exception: store error in meta_processing_error, mark row failed, continue
           Sleep between batches
```

**Critical design rule:** Part 3 (email) is structurally prevented from seeing Part 2 (improvements). The email must reflect only the *current* resume, not a hypothetical improved one.

---

## CSV Schema (68 Columns)

| Group | Columns | Count |
|---|---|---|
| Original (from Amazon CSV) | icimsJobId, title, jobLevel, companyName, ... | 33 |
| Canonical (prefixed `__`) | `__job_id`, `__title`, `__company`, `__location`, `__job_level`, `__department`, `__hiring_manager_name`, `__hiring_manager_email`, `__recruiter_name`, `__recruiter_email` | 10 |
| Merged description | `job_description_full` | 1 |
| Part 1 ATS | `ats_overall_score`, `ats_keyword_match_pct`, `ats_required_skills_matched/missing`, `ats_preferred_skills_matched/missing`, `ats_experience_level_match`, `ats_education_match`, `ats_title_alignment_score`, `ats_top_keywords_missing`, `ats_fit_summary` | 13 |
| Part 2 Improve | `improve_skills_to_add`, `improve_skills_to_emphasize`, `improve_experience_bullets`, `improve_resume_edit_prompt`, `improve_overall_strategy` | 5 |
| Part 3 Email | `email_subject`, `email_body` | 2 |
| Meta | `meta_processed_at`, `meta_llm_provider`, `meta_llm_model`, `meta_processing_error` | 4 |

Lists/dicts in columns are JSON-serialized strings.

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
    openai: "gpt-5.1"
    gemini: "gemini-1.5-pro"
  max_tokens: 4096
  json_retry_attempts: 2

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

`column_mapping` is what makes the system portable to other companies' CSVs — change just this block, no code changes needed.

---

## Dependencies

| Package | Purpose |
|---|---|
| `anthropic>=0.40.0` | Claude API |
| `openai>=1.50.0` | OpenAI API |
| `google-genai>=1.0.0` | Gemini API |
| `pdfplumber>=0.11.0` | PDF text extraction |
| `pandas>=2.2.0` | CSV / DataFrame operations |
| `pyyaml>=6.0` | Config file parsing |
| `python-dotenv>=1.0.0` | Load `.env` API keys |
| `rich>=13.7.0` | Terminal UI (progress bars, tables, colors) |
| `click>=8.1.0` | CLI framework |

Install: `pip install -r requirements.txt`

---

## How to Run

```bash
# Minimal — prompts interactively for LLM, API key, paths
python main.py

# Full specification
python main.py \
  --csv "data/input csv/amazon_jobs_clean.csv" \
  --resume data/resume/resume.pdf \
  --llm claude \
  --model claude-sonnet-4-6 \
  --limit 10

# Resume from checkpoint (skips already-processed rows automatically)
python main.py --csv "data/input csv/amazon_jobs_clean.csv" --llm openai

# Retry only failed rows
python main.py --csv "data/input csv/amazon_jobs_clean.csv" --llm openai --retry-failed

# Use a different config
python main.py --config custom_config.yaml
```

---

## What Is Implemented

- [x] LLM client abstraction (Claude, OpenAI, Gemini via factory pattern)
- [x] JSON retry logic (strips markdown fences, retries up to 2× on parse failure)
- [x] Resume PDF parsing → structured JSON
- [x] SHA256-based resume cache with delta detection
- [x] CSV preprocessing (column mapping, description merge, output schema pre-population)
- [x] ATS Analyzer (Part 1) — weighted scoring across skills/experience/education/title
- [x] Resume Improver (Part 2) — grounded suggestions only, includes resume_edit_prompt
- [x] Cold Email Generator (Part 3) — strict rules on length, tone, forbidden phrases
- [x] Batch processing with configurable delays
- [x] Checkpoint save/load (resume on interrupt)
- [x] Per-row error isolation (one failure doesn't stop the batch)
- [x] Rich CLI with progress bars and config tables

## What Is NOT Implemented (Roadmap)

- [ ] **Email sending** — emails are generated but not sent; SMTP / SendGrid not integrated
- [ ] **Recipient lookup** — `hm_email` / `recruiter_email` columns exist in CSV but are unused for sending
- [ ] **FastAPI REST API** — `plan.md` describes this as a future expansion; all service functions are already pure dicts-in/dicts-out, so wrapping is straightforward
- [ ] **Persistent logging** — only `rich.console` output, no log file
- [ ] **Database layer** — deliberately avoided; CSV + checkpoints is the full data layer
- [ ] **Result search/filter** — no query interface; open the CSV in Excel/pandas manually
- [ ] **Resume version history** — cache detects changes but stores only the latest parse

---

## Key Implementation Notes

**LLM Client pattern** (`src/llm/base.py`):
- `complete(system, user)` → raw string
- `complete_json(system, user)` → parsed dict (retries on JSON failure)
- Each provider subclass overrides `_call(system, user) → str`
- Gemini has no separate system role — base class concatenates `system + "\n\n---\n\n" + user`

**Resume cache** (`src/resume/cache.py`):
- Cache key is SHA256 of the PDF bytes
- On hash mismatch: re-parse and print a colored delta of what changed
- Cache file path: `data/resume_cache.json`

**Column mapping** (`src/csv/preprocessor.py`):
- Canonical columns are always `__prefixed` — safe to reference in analysis code regardless of source CSV schema
- `job_description_full` is built by concatenating the `description_columns` list with section headers

**Checkpoint format** (`src/processor.py`):
```json
{
  "processed_row_ids": ["id1", "id2", ...],
  "failed_row_ids": ["id3", ...],
  "last_updated": "2026-05-07T01:49:24"
}
```

**Prompts** (`src/prompts.py`):
- All four prompt pairs live here: RESUME_PARSER, ATS_ANALYZER, IMPROVER, EMAIL_GENERATOR
- Each is a `(SYSTEM, USER)` pair where USER is a Python format string with `{resume_json}`, `{job_description}`, etc.
- Edit prompts here to tune LLM output quality without touching analysis code

---

## Environment Setup

```bash
# API keys in .env (copy from .env.example)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AI...
```

The `.env` file is gitignored. API keys are never committed.

---

## Session Log

| Date | What Changed | LLM Used |
|---|---|---|
| 2026-05-07 | Initial commit: full system built. 3/271 rows processed as smoke test. | openai / gpt-5.1 |

> Add a row here at the end of each session summarizing what changed.
