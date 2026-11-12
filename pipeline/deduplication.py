
"""
Twig Deliverable 1 - Job Deduplication

Reads accepted extracted jobs and removes
duplicate job postings.

Input:
    data/extracted_jobs.jsonl

Outputs:
    data/deduplicated_jobs.jsonl
    data/duplicate_jobs.jsonl

No Gemini API calls required.
"""

import hashlib
import json
import re
import unicodedata
from pathlib import Path

from .config import ROOT


DATA_DIR = ROOT / "data"

INPUT_FILE = DATA_DIR / "extracted_jobs.jsonl"
OUTPUT_FILE = DATA_DIR / "deduplicated_jobs.jsonl"
DUPLICATES_FILE = DATA_DIR / "duplicate_jobs.jsonl"


def normalize_text(value):
    """Normalize text for duplicate comparison."""
    if value is None:
        return ""

    value = unicodedata.normalize(
        "NFKC", str(value)
    )

    value = value.casefold().strip()

    value = re.sub(r"[^\w\s]", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def normalize_company(value):
    """Normalize common company suffixes."""
    company = normalize_text(value)

    company = re.sub(
        r"\b(inc|incorporated|llc|ltd|limited|corp|corporation)\b",
        "",
        company
    )

    return re.sub(r"\s+", " ", company).strip()


def identity_key(record):
    """
    Stable source-specific identifier.
    """
    source = normalize_text(record.get("source"))
    source_id = normalize_text(record.get("source_id"))

    if source and source_id:
        return f"{source}:{source_id}"

    return None


def content_key(record):
    """
    Compare company, job title and location.

    This is a conservative exact-match approach.
    """
    job = record.get("data") or {}

    parts = [
        normalize_company(job.get("company")),
        normalize_text(job.get("title")),
        normalize_text(job.get("city")),
        normalize_text(job.get("country")),
    ]

    # Avoid matching incomplete jobs.
    if not parts[0] or not parts[1]:
        return None

    if not parts[2] and not parts[3]:
        return None

    return "|".join(parts)


def job_key(record):
    """
    Generate a stable fingerprint for storage.
    """
    content = content_key(record)

    if content:
        raw_key = f"content:{content}"
    else:
        raw_key = (
            identity_key(record)
            or record.get("source_record_key")
            or json.dumps(record, sort_keys=True)
        )

    return hashlib.sha256(
        raw_key.encode("utf-8")
    ).hexdigest()


def load_jsonl(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Missing input file: {path}"
        )

    rows = []

    with path.open(
        "r",
        encoding="utf-8"
    ) as file:
        for line in file:
            if line.strip():
                rows.append(json.loads(line))

    return rows


def write_jsonl(path, rows):
    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    temporary = path.with_suffix(
        path.suffix + ".tmp"
    )

    with temporary.open(
        "w",
        encoding="utf-8"
    ) as file:
        for row in rows:
            file.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    default=str
                ) + "\n"
            )

    temporary.replace(path)


def deduplicate(records):
    """
    Remove duplicate postings.

    Different source IDs are not automatically
    considered different jobs.

    Different jobs from the same HN comment
    are also not automatically duplicates.
    """
    unique = []
    duplicates = []

    seen_content = {}
    seen_source_jobs = {}

    for record in records:
        content = content_key(record)
        identity = identity_key(record)

        source_job_key = (
            (identity, content)
            if identity and content
            else None
        )

        duplicate_of = None
        reason = None

        if content and content in seen_content:
            duplicate_of = seen_content[content]
            reason = "matching_company_title_location"

        elif (
            source_job_key
            and source_job_key in seen_source_jobs
        ):
            duplicate_of = seen_source_jobs[
                source_job_key
            ]
            reason = "matching_source_and_job"

        if duplicate_of is not None:
            duplicates.append({
                **record,
                "duplicate_of": duplicate_of,
                "duplicate_reason": reason,
            })
            continue

        fingerprint = job_key(record)

        unique_record = {
            **record,
            "job_key": fingerprint,
        }

        unique.append(unique_record)

        if content:
            seen_content[content] = fingerprint

        if source_job_key:
            seen_source_jobs[
                source_job_key
            ] = fingerprint

    return unique, duplicates


def run():
    records = load_jsonl(INPUT_FILE)

    unique, duplicates = deduplicate(records)

    write_jsonl(OUTPUT_FILE, unique)
    write_jsonl(DUPLICATES_FILE, duplicates)

    print("\n" + "=" * 55)
    print("JOB DEDUPLICATION SUMMARY")
    print("=" * 55)

    print("Input jobs:", len(records))
    print("Unique jobs:", len(unique))
    print("Duplicates removed:", len(duplicates))

    print("\nUnique output:", OUTPUT_FILE)
    print("Duplicates output:", DUPLICATES_FILE)

    if duplicates:
        print("\nDUPLICATE DETAILS")

        for index, record in enumerate(
            duplicates,
            start=1
        ):
            job = record.get("data") or {}

            print(
                f"{index}. "
                f"{job.get('company')} | "
                f"{job.get('title')} | "
                f"{job.get('city')}"
            )

            print(
                "Reason:",
                record.get("duplicate_reason")
            )


if __name__ == "__main__":
    run()
