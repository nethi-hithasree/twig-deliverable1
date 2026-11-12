
import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
USAGE_FILE = DATA_DIR / "llm_usage.jsonl"

# USD per 1 million tokens.
# Set these to the verified pricing for your Gemini model.
INPUT_PRICE = float(os.getenv("GEMINI_INPUT_PRICE_PER_M", "0"))
OUTPUT_PRICE = float(os.getenv("GEMINI_OUTPUT_PRICE_PER_M", "0"))


def calculate_cost(input_tokens, output_tokens):
    return (
        input_tokens * INPUT_PRICE / 1_000_000
        + output_tokens * OUTPUT_PRICE / 1_000_000
    )


def generate_report():
    if not USAGE_FILE.exists():
        raise FileNotFoundError(
            f"Usage file not found: {USAGE_FILE}"
        )

    with USAGE_FILE.open("r", encoding="utf-8") as f:
        rows = [
            json.loads(line)
            for line in f
            if line.strip()
        ]

    input_tokens = sum(
        row.get("input_tokens", 0) for row in rows
    )

    output_tokens = sum(
        row.get("output_tokens", 0) for row in rows
    )

    total_tokens = sum(
        row.get("total_tokens", 0) for row in rows
    )

    cache_hits = sum(
        bool(row.get("cached")) for row in rows
    )

    # Historical estimated cost for these records.
    historical_cost = calculate_cost(
        input_tokens, output_tokens
    )

    # Estimated cost of API calls in the latest run.
    new_input_tokens = sum(
        row.get("input_tokens", 0)
        for row in rows
        if not row.get("cached")
    )

    new_output_tokens = sum(
        row.get("output_tokens", 0)
        for row in rows
        if not row.get("cached")
    )

    latest_run_cost = calculate_cost(
        new_input_tokens, new_output_tokens
    )

    pricing_configured = (
        INPUT_PRICE > 0 and OUTPUT_PRICE > 0
    )

    report = {
        "records": len(rows),
        "model": sorted({
            row.get("model", "unknown")
            for row in rows
        }),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cache_hits": cache_hits,
        "new_api_calls": len(rows) - cache_hits,
        "pricing_configured": pricing_configured,
        "historical_estimated_cost_usd": (
            round(historical_cost, 6)
            if pricing_configured else None
        ),
        "latest_run_estimated_cost_usd": (
            round(latest_run_cost, 6)
            if pricing_configured else None
        ),
    }

    output_path = DATA_DIR / "cost_report.json"

    output_path.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8"
    )

    print(json.dumps(report, indent=2))

    print("\nReport saved to:", output_path)


if __name__ == "__main__":
    generate_report()
