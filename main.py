#!/usr/bin/env python3
"""
Job Application Automation — CLI entry point.

Usage:
    python main.py
    python main.py --csv path/to/jobs.csv --resume path/to/resume.pdf
    python main.py --limit 5          # process only first 5 rows (for testing)
    python main.py --retry-failed     # reprocess rows that errored last run
    python main.py --config custom_config.yaml
"""

import os
import sys

import click
import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from src.csv.preprocessor import load_and_normalize, save_preprocessed
from src.llm.factory import DEFAULT_MODELS, PROVIDERS, create_client
from src.processor import process_csv
from src.resume.cache import get_resume_json

load_dotenv()
console = Console()


def _load_config(config_path: str) -> dict:
    if not os.path.exists(config_path):
        console.print(f"[red]Config file not found:[/red] {config_path}")
        sys.exit(1)
    with open(config_path) as f:
        return yaml.safe_load(f)


def _resolve_api_key(provider: str, provided_key: str | None) -> str:
    """Return API key from CLI arg, then .env, then prompt."""
    if provided_key and provided_key.strip():
        return provided_key.strip()

    env_map = {
        "claude": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "gemini": "GOOGLE_API_KEY",
    }
    env_key = os.getenv(env_map.get(provider, ""))
    if env_key and env_key.strip():
        console.print(f"  Using API key from environment variable [cyan]{env_map[provider]}[/cyan]")
        return env_key.strip()

    return Prompt.ask(f"  Enter your {provider.capitalize()} API key", password=True)


@click.command()
@click.option("--csv", "csv_path", default=None, help="Path to input jobs CSV file")
@click.option("--resume", "resume_path", default=None, help="Path to resume PDF")
@click.option(
    "--llm",
    "llm_provider",
    default=None,
    type=click.Choice(list(PROVIDERS.keys()), case_sensitive=False),
    help="LLM provider to use",
)
@click.option("--api-key", "api_key", default=None, help="API key (overrides .env)")
@click.option("--model", default=None, help="Override default model name")
@click.option("--limit", default=None, type=int, help="Process only first N unprocessed rows (useful for testing)")
@click.option("--retry-failed", "retry_failed", is_flag=True, default=False, help="Reprocess rows that errored in a previous run")
@click.option("--config", "config_path", default="config.yaml", help="Path to config.yaml")
def main(csv_path, resume_path, llm_provider, api_key, model, limit, retry_failed, config_path):
    console.print(Panel.fit("[bold cyan]Job Application Automation[/bold cyan]", border_style="cyan"))

    cfg = _load_config(config_path)
    processing = cfg.get("processing", {})
    llm_cfg = cfg.get("llm", {})
    resume_cfg = cfg.get("resume", {})
    csv_cfg = cfg.get("csv", {})

    # --- LLM selection ---
    if not llm_provider:
        llm_provider = Prompt.ask(
            "\nWhich LLM do you want to use?",
            choices=list(PROVIDERS.keys()),
            default="claude",
        )

    resolved_api_key = _resolve_api_key(llm_provider, api_key)

    if not model:
        default_model = llm_cfg.get("default_models", DEFAULT_MODELS).get(llm_provider, DEFAULT_MODELS[llm_provider])
        model_input = Prompt.ask(
            f"  Model (press Enter for default [cyan]{default_model}[/cyan])",
            default=default_model,
        )
        model = model_input or default_model

    console.print(f"\n[green]LLM:[/green] {llm_provider} / {model}")

    llm_client = create_client(
        provider=llm_provider,
        api_key=resolved_api_key,
        model=model,
        max_tokens=llm_cfg.get("max_tokens", 4096),
        json_retry_attempts=llm_cfg.get("json_retry_attempts", 2),
    )

    # --- Resume ---
    default_resume = resume_cfg.get("pdf_path", "data/resume/resume.pdf")
    if not resume_path:
        resume_path = Prompt.ask(f"\nPath to resume PDF", default=default_resume)

    cache_path = resume_cfg.get("cache_path", "data/resume_cache.json")
    console.print()
    resume_json = get_resume_json(resume_path, cache_path, llm_client)

    # --- CSV ---
    if not csv_path:
        csv_path = Prompt.ask("\nPath to input jobs CSV")

    column_mapping = csv_cfg.get("column_mapping", {})
    description_columns = csv_cfg.get("description_columns", ["description"])
    id_column = csv_cfg.get("id_column", "id")

    console.print()
    df = load_and_normalize(csv_path, column_mapping, description_columns, id_column)
    output_csv_path = save_preprocessed(df, csv_path)

    # Reload the saved CSV so dtypes are consistent
    import pandas as pd
    df = pd.read_csv(output_csv_path, dtype=str).fillna("")

    if limit:
        console.print(f"[yellow]Limit set:[/yellow] processing at most {limit} unprocessed rows")

    # --- Process ---
    console.print()
    process_csv(
        df=df,
        output_csv_path=output_csv_path,
        resume_json=resume_json,
        llm_client=llm_client,
        provider=llm_provider,
        model=model,
        batch_size=processing.get("batch_size", 10),
        delay_between_rows=processing.get("delay_between_rows_sec", 1),
        delay_between_batches=processing.get("delay_between_batches_sec", 5),
        id_column=id_column,
        checkpoint_dir="data/checkpoints",
        limit=limit,
        retry_failed=retry_failed,
    )


if __name__ == "__main__":
    main()
