import hashlib
import json
import os
from datetime import datetime, timezone

from rich.console import Console
from rich.table import Table

from src.llm.base import LLMClient
from src.resume.parser import extract_text_from_pdf, parse_resume_with_llm

console = Console()


def _compute_pdf_hash(pdf_path: str) -> str:
    with open(pdf_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _load_cache(cache_path: str) -> dict | None:
    if not os.path.exists(cache_path):
        return None
    with open(cache_path) as f:
        return json.load(f)


def _save_cache(cache_path: str, pdf_hash: str, resume_json: dict) -> None:
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    cache = {
        "pdf_hash": pdf_hash,
        "parsed_at": datetime.now(timezone.utc).isoformat(),
        "resume_json": resume_json,
    }
    with open(cache_path, "w") as f:
        json.dump(cache, f, indent=2)


def _print_delta(old: dict, new: dict) -> None:
    """Show which top-level sections of the resume JSON changed."""
    table = Table(title="Resume Cache Delta", show_header=True)
    table.add_column("Section", style="cyan")
    table.add_column("Status", style="bold")

    all_keys = set(old) | set(new)
    for key in sorted(all_keys):
        if key not in old:
            table.add_row(key, "[green]ADDED[/green]")
        elif key not in new:
            table.add_row(key, "[red]REMOVED[/red]")
        elif old[key] != new[key]:
            table.add_row(key, "[yellow]CHANGED[/yellow]")
        else:
            table.add_row(key, "[dim]unchanged[/dim]")

    console.print(table)


def get_resume_json(pdf_path: str, cache_path: str, llm_client: LLMClient) -> dict:
    """
    Return the structured resume JSON.
    Uses cached version if PDF has not changed since last parse.
    Re-parses and updates cache if PDF hash differs.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Resume PDF not found: {pdf_path}")

    current_hash = _compute_pdf_hash(pdf_path)
    cache = _load_cache(cache_path)

    if cache and cache.get("pdf_hash") == current_hash:
        console.print(f"[green]Resume unchanged[/green] — using cached parse from {cache['parsed_at']}")
        return cache["resume_json"]

    if cache:
        console.print("[yellow]Resume PDF has changed — re-parsing with LLM...[/yellow]")
    else:
        console.print("[blue]No resume cache found — parsing PDF with LLM...[/blue]")

    raw_text = extract_text_from_pdf(pdf_path)
    console.print(f"  Extracted {len(raw_text):,} characters from PDF")

    new_resume_json = parse_resume_with_llm(raw_text, llm_client)
    _save_cache(cache_path, current_hash, new_resume_json)
    console.print(f"[green]Resume parsed and cached → {cache_path}[/green]")

    if cache and cache.get("resume_json"):
        _print_delta(cache["resume_json"], new_resume_json)

    return new_resume_json
