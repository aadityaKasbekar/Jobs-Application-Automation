import json

import pandas as pd


def write_row_results(df: pd.DataFrame, row_idx: int, results: dict) -> None:
    """
    Write a flat dict of results into the DataFrame at the given integer index.
    Lists and dicts are JSON-serialized to strings for CSV storage.
    """
    for col, value in results.items():
        if isinstance(value, (dict, list)):
            df.at[row_idx, col] = json.dumps(value, ensure_ascii=False)
        else:
            df.at[row_idx, col] = value if value is not None else ""


def save_csv(df: pd.DataFrame, output_path: str) -> None:
    df.to_csv(output_path, index=False)
