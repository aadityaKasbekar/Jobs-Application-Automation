import json
import os
import time
from datetime import datetime, timezone

import pandas as pd
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from src.analysis import ats_analyzer, emailer, improver
from src.csv.writer import save_csv, write_row_results
from src.llm.base import LLMClient

console = Console()


def _checkpoint_path(csv_path: str, checkpoint_dir: str) -> str:
    stem = os.path.splitext(os.path.basename(csv_path))[0]
    os.makedirs(checkpoint_dir, exist_ok=True)
    return os.path.join(checkpoint_dir, f"{stem}_checkpoint.json")


def _load_checkpoint(checkpoint_path: str) -> dict:
    if not os.path.exists(checkpoint_path):
        return {"processed_row_ids": [], "failed_row_ids": []}
    with open(checkpoint_path) as f:
        return json.load(f)


def _save_checkpoint(checkpoint_path: str, data: dict) -> None:
    data["last_saved_at"] = datetime.now(timezone.utc).isoformat()
    with open(checkpoint_path, "w") as f:
        json.dump(data, f, indent=2)


def process_csv(
    df: pd.DataFrame,
    output_csv_path: str,
    resume_json: dict,
    llm_client: LLMClient,
    provider: str,
    model: str,
    batch_size: int = 10,
    delay_between_rows: float = 1.0,
    delay_between_batches: float = 5.0,
    id_column: str = "icimsJobId",
    checkpoint_dir: str = "data/checkpoints",
    limit: int | None = None,
    retry_failed: bool = False,
) -> None:
    checkpoint_file = _checkpoint_path(output_csv_path, checkpoint_dir)
    checkpoint = _load_checkpoint(checkpoint_file)

    already_done = set(checkpoint.get("processed_row_ids", []))
    already_failed = set(checkpoint.get("failed_row_ids", []))

    skip_ids = already_done.copy()
    if not retry_failed:
        skip_ids |= already_failed

    rows_to_process = []
    for idx, row in df.iterrows():
        row_id = str(row.get(id_column, idx))
        if row_id not in skip_ids:
            rows_to_process.append((idx, row_id, row))

    if limit:
        rows_to_process = rows_to_process[:limit]

    total = len(rows_to_process)
    if total == 0:
        console.print("[green]All rows already processed. Nothing to do.[/green]")
        if already_failed:
            console.print(f"[yellow]{len(already_failed)} failed rows exist. Use --retry-failed to reprocess them.[/yellow]")
        return

    console.print(
        f"\nProcessing [cyan]{total}[/cyan] rows "
        f"([dim]{len(already_done)} already done, {len(already_failed)} failed[/dim])\n"
    )

    processed_ids = list(already_done)
    failed_ids = list(already_failed) if not retry_failed else []
    completed = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Analyzing jobs...", total=total)

        for batch_start in range(0, total, batch_size):
            batch = rows_to_process[batch_start : batch_start + batch_size]

            for idx, row_id, row in batch:
                job_row = row.to_dict()
                title = job_row.get("__title", job_row.get("title", row_id))
                company = job_row.get("__company", job_row.get("companyName", ""))

                progress.update(task, description=f"[cyan]{company}[/cyan] — {title[:50]}")

                error_msg = ""
                row_results: dict = {}

                try:
                    # Part 1
                    ats_results = ats_analyzer.analyze(resume_json, job_row, llm_client)
                    row_results.update({k: v for k, v in ats_results.items() if not k.startswith("_")})
                    time.sleep(delay_between_rows)

                    # Part 2
                    improve_results = improver.improve(resume_json, job_row, ats_results, llm_client)
                    row_results.update(improve_results)
                    time.sleep(delay_between_rows)

                    # Part 3
                    email_results = emailer.generate_email(resume_json, job_row, llm_client)
                    row_results.update(email_results)

                    processed_ids.append(row_id)
                    score = ats_results.get("ats_overall_score", "?")
                    console.log(f"  [green]✓[/green] {company} | {title[:40]} | ATS: {score}")

                except Exception as e:
                    error_msg = str(e)
                    failed_ids.append(row_id)
                    console.log(f"  [red]✗[/red] {company} | {title[:40]} | Error: {error_msg[:80]}")

                row_results["meta_processed_at"] = datetime.now(timezone.utc).isoformat()
                row_results["meta_llm_provider"] = provider
                row_results["meta_llm_model"] = model
                row_results["meta_processing_error"] = error_msg

                write_row_results(df, idx, row_results)
                save_csv(df, output_csv_path)

                completed += 1
                progress.advance(task)

            # Save checkpoint after each batch
            _save_checkpoint(
                checkpoint_file,
                {
                    "csv_path": output_csv_path,
                    "processed_row_ids": processed_ids,
                    "failed_row_ids": failed_ids,
                    "total_rows": len(df),
                    "completed_rows": len(processed_ids),
                },
            )
            console.print(
                f"  [dim]Checkpoint saved — {len(processed_ids)} done, {len(failed_ids)} failed[/dim]"
            )

            if batch_start + batch_size < total:
                time.sleep(delay_between_batches)

    console.print(
        f"\n[bold green]Done![/bold green] "
        f"{len(processed_ids)} processed, {len(failed_ids)} failed. "
        f"Output → [cyan]{output_csv_path}[/cyan]"
    )
    if failed_ids:
        console.print(f"[yellow]Failed row IDs:[/yellow] {failed_ids}")
        console.print("Re-run with [bold]--retry-failed[/bold] to retry them.")
