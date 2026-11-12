
import argparse
import json
import re
from collections import Counter
from pathlib import Path

from .config import ROOT
from .filters import is_relevant_title

DATA_DIR = ROOT / "data"
INPUT_FILE = DATA_DIR / "scraped_jobs.jsonl"
OUTPUT_FILE = DATA_DIR / "prefiltered_jobs.jsonl"
REVIEW_FILE = DATA_DIR / "prefilter_review.jsonl"

MULTI_ROLE = re.compile(
    r"\b(?:multiple (?:roles|positions|openings)|"
    r"various (?:roles|positions)|"
    r"several (?:roles|positions)|"
    r"we(?:'re| are) hiring|"
    r"open positions|"
    r"engineering roles)\b",
    re.IGNORECASE,
)

POSSIBLE_ROLE = re.compile(
    r"\b(?:machine learning|data science|"
    r"data engineering|analytics engineering|"
    r"platform engineering|mlops|"
    r"ai/ml|data platform|"
    r"data infrastructure)\b",
    re.IGNORECASE,
)

UNRELATED_TITLE = re.compile(
    r"\b(?:java developer|frontend developer|"
    r"front-end developer|"
    r"sales representative|"
    r"account executive|"
    r"graphic designer|"
    r"customer support)\b",
    re.IGNORECASE,
)


def classify_candidate(record):
    """
    Classify source records without using an LLM.

    This is a prioritization step, not final
    job validation.
    """
    source = record.get("source", "")
    title = record.get("title_raw") or ""
    description = record.get("description_raw") or ""

    if source != "hackernews":
        return "high_priority", "Structured source candidate"

    # HN comments usually begin with a heading.
    header = description[:300]

    if is_relevant_title(header):
        return "high_priority", "Relevant role in heading"

    if MULTI_ROLE.search(header):
        return "needs_review", "Possible multiple job roles"

    if POSSIBLE_ROLE.search(description):
        return "needs_review", "Relevant technical role signal"

    if UNRELATED_TITLE.search(header):
        return "low_priority", "Unrelated role in heading"

    return "needs_review", "Insufficient role information"


def load_jsonl(path):
    if not path.exists():
        raise FileNotFoundError(path)

    with path.open(encoding="utf-8") as file:
        return [
            json.loads(line)
            for line in file
            if line.strip()
        ]


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(
                json.dumps(
                    row,
                    ensure_ascii=False
                ) + "\n"
            )


def run():
    records = load_jsonl(INPUT_FILE)

    prioritized = []
    review = []
    counts = Counter()

    for record in records:
        priority, reason = classify_candidate(record)

        enriched = {
            **record,
            "prefilter_priority": priority,
            "prefilter_reason": reason,
        }

        counts[priority] += 1

        if priority == "low_priority":
            review.append(enriched)
        else:
            prioritized.append(enriched)

    write_jsonl(OUTPUT_FILE, prioritized)
    write_jsonl(REVIEW_FILE, review)

    print("\n" + "=" * 55)
    print("CANDIDATE PREFILTER SUMMARY")
    print("=" * 55)

    print("Input candidates:", len(records))
    print("High priority:", counts["high_priority"])
    print("Needs review:", counts["needs_review"])
    print("Low priority:", counts["low_priority"])
    print("Candidates retained:", len(prioritized))

    print("\nOutput:", OUTPUT_FILE)
    print("Low-priority review:", REVIEW_FILE)


if __name__ == "__main__":
    run()
