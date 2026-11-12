
"""Batch Gemini extraction with prefilter priority, caching, and auditing."""

import argparse
import hashlib
import json
import logging
import random
import re
import time
from pathlib import Path

from google.genai import errors
from pydantic import ValidationError

from .config import ROOT
from .extractor import (
    extract_jobs,
    get_client,
    MODEL_NAME,
    clean_description,
)
from .validator import validate_job
from .schemas import JobExtraction
from .scraper_utils import utc_now


logger = logging.getLogger(__name__)

DATA_DIR = ROOT / "data"

INPUT_FILE = DATA_DIR / "prefiltered_jobs.jsonl"
FALLBACK_INPUT = DATA_DIR / "scraped_jobs.jsonl"

OUTPUT_FILE = DATA_DIR / "extracted_jobs.jsonl"
REJECTED_FILE = DATA_DIR / "rejected_jobs.jsonl"
USAGE_FILE = DATA_DIR / "llm_usage.jsonl"
ERROR_FILE = DATA_DIR / "processing_errors.jsonl"

CACHE_DIR = DATA_DIR / "extraction_cache"

# Preserve existing cache identity.
EXTRACTION_VERSION = "v2-clean-html"

MIN_REQUEST_INTERVAL = 5.0
MAX_RETRIES = 3
BASE_RETRY_DELAY = 10.0
MAX_RETRY_DELAY = 120.0


# ---------------------------------------------------------
# RECORD IDENTIFICATION
# ---------------------------------------------------------

def record_key(record):
    identity = {
        k: record.get(k)
        for k in ("source", "source_id", "source_url")
    }

    return hashlib.sha256(
        json.dumps(
            identity,
            sort_keys=True
        ).encode("utf-8")
    ).hexdigest()


def cache_key(record):
    content = {
        "identity": record_key(record),
        "title": record.get("title_raw"),
        "company": record.get("company_raw"),
        "location": record.get("location_raw"),
        "description": record.get("description_raw"),
        "model": MODEL_NAME,
        "version": EXTRACTION_VERSION,
    }

    return hashlib.sha256(
        json.dumps(
            content,
            sort_keys=True,
            ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()


# ---------------------------------------------------------
# INPUT LOADING
# ---------------------------------------------------------

def load_records(input_path=INPUT_FILE, priority="all"):

    if not input_path.exists():
        raise FileNotFoundError(
            f"Missing input file: {input_path}"
        )

    unique = {}

    with input_path.open("r", encoding="utf-8") as stream:

        for line_number, line in enumerate(stream, 1):

            if not line.strip():
                continue

            try:
                record = json.loads(line)

            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON on {input_path}:{line_number}"
                ) from exc

            if not isinstance(record, dict):
                raise ValueError(
                    f"Expected JSON object on {input_path}:{line_number}"
                )

            unique[record_key(record)] = record

    records = list(unique.values())

    if priority != "all":
        records = [
            r for r in records
            if r.get("prefilter_priority") == priority
        ]

    records.sort(
        key=lambda r: (
            0 if r.get("prefilter_priority") == "high_priority" else 1,
            str(r.get("source") or ""),
            str(r.get("source_id") or ""),
        )
    )

    return records


# ---------------------------------------------------------
# JSONL FILE HANDLING
# ---------------------------------------------------------

def write_jsonl(path, records):

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    temporary = path.with_suffix(
        path.suffix + ".tmp"
    )

    with temporary.open("w", encoding="utf-8") as stream:

        for record in records:

            stream.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                    default=str
                ) + "\n"
            )

    temporary.replace(path)


# ---------------------------------------------------------
# EXTRACTION CACHE
# ---------------------------------------------------------

def read_cache(key):

    path = CACHE_DIR / f"{key}.json"

    if not path.exists():
        return None

    try:
        payload = json.loads(
            path.read_text(encoding="utf-8")
        )

        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("jobs"), list)
        ):
            raise ValueError("Invalid cache structure")

        return payload

    except (OSError, ValueError, TypeError):
        logger.warning(
            "Ignoring invalid extraction cache: %s",
            path
        )

        return None


def save_cache(key, payload):

    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    path = CACHE_DIR / f"{key}.json"
    temporary = path.with_suffix(".tmp")

    temporary.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
            default=str
        ),
        encoding="utf-8"
    )

    temporary.replace(path)


# ---------------------------------------------------------
# SOURCE TEXT FOR VALIDATION
# ---------------------------------------------------------

def build_source_text(record):

    description = clean_description(
        record.get("description_raw") or ""
    )

    return "\n".join([
        f"Company: {record.get('company_raw') or ''}",
        f"Title: {record.get('title_raw') or ''}",
        f"Location: {record.get('location_raw') or ''}",
        f"Description: {description}",
    ])[:20000]


# ---------------------------------------------------------
# ERROR HANDLING
# ---------------------------------------------------------

def error_row(record, exc, stage):

    return {
        "source_record_key": record_key(record),
        "source": record.get("source"),
        "source_id": record.get("source_id"),
        "source_url": record.get("source_url"),
        "stage": stage,
        "error_type": type(exc).__name__,
        "message": str(exc),
        "timestamp": utc_now(),
    }


def rejected_row(record, data=None, warnings=None):

    return {
        "source_record_key": record_key(record),
        "source": record.get("source"),
        "source_id": record.get("source_id"),
        "source_url": record.get("source_url"),
        "data": data,
        "warnings": warnings or [],
    }


def is_quota_error(exc):

    message = str(exc).lower()

    return (
        "429" in message
        or "resource_exhausted" in message
        or "quota exceeded" in message
    )


def retry_delay(exc, attempt):

    message = str(exc)

    match = re.search(
        r"retry in\s+([\d.]+)\s*s",
        message,
        flags=re.IGNORECASE
    )

    if match:
        return min(
            float(match.group(1)) + 2,
            MAX_RETRY_DELAY
        )

    return min(
        BASE_RETRY_DELAY * (2 ** attempt)
        + random.uniform(0, 2),
        MAX_RETRY_DELAY
    )


# ---------------------------------------------------------
# GEMINI EXTRACTION
# ---------------------------------------------------------

def process_record(record, client):

    key = cache_key(record)

    cached = read_cache(key)

    if cached is not None:
        return cached, True

    result, usage = extract_jobs(
        record,
        client=client
    )

    payload = {
        "source_record_key": record_key(record),
        "source": record.get("source"),
        "source_id": record.get("source_id"),
        "source_url": record.get("source_url"),
        "model": MODEL_NAME,
        "processed_at": utc_now(),
        "jobs": result.model_dump(mode="json")["jobs"],
        "usage": usage,
    }

    save_cache(key, payload)

    return payload, False


def extract_with_retry(record, client):

    for attempt in range(MAX_RETRIES):

        try:
            return process_record(record, client)

        except (
            errors.ClientError,
            errors.ServerError
        ) as exc:

            if not (
                is_quota_error(exc)
                or isinstance(exc, errors.ServerError)
            ):
                raise

            if attempt == MAX_RETRIES - 1:
                raise

            delay = retry_delay(exc, attempt)

            logger.warning(
                "Gemini request failed. "
                "Retrying in %.1f seconds",
                delay
            )

            time.sleep(delay)

    raise RuntimeError(
        "Gemini extraction failed after retries"
    )


# ---------------------------------------------------------
# JOB VALIDATION
# ---------------------------------------------------------

def validate_extracted_jobs(record, payload):

    accepted = []
    rejected = []
    errors_found = []

    source_text = build_source_text(record)

    jobs = payload.get("jobs") or []

    if not jobs:

        rejected.append(
            rejected_row(
                record,
                warnings=[
                    "LLM returned no relevant roles"
                ]
            )
        )

        return accepted, rejected, errors_found

    for job_data in jobs:

        try:

            job = JobExtraction.model_validate(
                job_data
            )

            validated, warnings = validate_job(
                job,
                source_text
            )

            row = {
                "source_record_key": record_key(record),
                "source": record.get("source"),
                "source_id": record.get("source_id"),
                "source_url": record.get("source_url"),
                "data": (
                    validated.model_dump(mode="json")
                    if validated is not None
                    else job.model_dump(mode="json")
                ),
                "warnings": warnings,
            }

            if validated is not None:
                accepted.append(row)

            else:
                rejected.append(row)

        except (
            ValidationError,
            ValueError,
            TypeError,
            AttributeError
        ) as exc:

            errors_found.append(
                error_row(
                    record,
                    exc,
                    "job_validation"
                )
            )

            rejected.append(
                rejected_row(
                    record,
                    data=job_data,
                    warnings=[
                        f"Job validation failed: {type(exc).__name__}"
                    ]
                )
            )

    return accepted, rejected, errors_found


# ---------------------------------------------------------
# MAIN BATCH PROCESSOR
# ---------------------------------------------------------

def run(
    limit=3,
    cache_only=False,
    max_api_requests=None,
    priority="all",
    input_path=None
):

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )

    if input_path is None:

        input_path = (
            INPUT_FILE
            if INPUT_FILE.exists()
            else FALLBACK_INPUT
        )

    input_path = Path(input_path)

    records = load_records(
        input_path=input_path,
        priority=priority
    )

    if limit is not None:
        records = records[:limit]

    print(
        f"\nProcessing {len(records)} source records",
        flush=True
    )

    print(
        f"Input file: {input_path}",
        flush=True
    )

    extracted = []
    rejected = []
    usage_rows = []
    processing_errors = []

    cache_hits = 0
    api_requests = 0
    cache_misses_skipped = 0

    client = None
    last_api_request = None

    for index, record in enumerate(records, 1):

        print(
            f"\n[{index}/{len(records)}] "
            f"{record.get('source')} | "
            f"{record.get('title_raw') or 'HN comment'}",
            flush=True
        )

        cached = read_cache(
            cache_key(record)
        )

        if cached is not None:

            payload = cached
            from_cache = True
            cache_hits += 1

            print("Using cached LLM result")

        else:

            if cache_only:

                cache_misses_skipped += 1
                print("Cache missing - skipped")
                continue

            if (
                max_api_requests is not None
                and api_requests >= max_api_requests
            ):

                cache_misses_skipped += 1
                print("API request limit reached - skipped")
                continue

            try:

                if client is None:
                    client = get_client()

                if last_api_request is not None:

                    elapsed = (
                        time.monotonic()
                        - last_api_request
                    )

                    if elapsed < MIN_REQUEST_INTERVAL:
                        time.sleep(
                            MIN_REQUEST_INTERVAL - elapsed
                        )

                # Counts source records submitted for API
                # extraction, not individual retry attempts.
                api_requests += 1
                last_api_request = time.monotonic()

                payload, from_cache = extract_with_retry(
                    record,
                    client
                )

                print("Gemini extraction successful")

            except Exception as exc:

                logger.exception(
                    "Processing failed for source %s",
                    record.get("source_id")
                )

                processing_errors.append(
                    error_row(
                        record,
                        exc,
                        "source_processing"
                    )
                )

                rejected.append(
                    rejected_row(
                        record,
                        warnings=[
                            f"Processing failed: {type(exc).__name__}"
                        ]
                    )
                )

                continue

        usage = payload.get("usage") or {}

        if not isinstance(usage, dict):
            usage = {"raw_usage": usage}

        usage_rows.append({
            "source_record_key": record_key(record),
            "source": record.get("source"),
            "cached": from_cache,
            **usage,
        })

        accepted_rows, rejected_rows, job_errors = (
            validate_extracted_jobs(
                record,
                payload
            )
        )

        extracted.extend(accepted_rows)
        rejected.extend(rejected_rows)
        processing_errors.extend(job_errors)

    # -----------------------------------------------------
    # WRITE OUTPUTS
    # -----------------------------------------------------

    write_jsonl(
        OUTPUT_FILE,
        extracted
    )

    write_jsonl(
        REJECTED_FILE,
        rejected
    )

    write_jsonl(
        USAGE_FILE,
        usage_rows
    )

    write_jsonl(
        ERROR_FILE,
        processing_errors
    )

    # -----------------------------------------------------
    # SUMMARY
    # -----------------------------------------------------

    print("\n" + "=" * 55)
    print("BATCH EXTRACTION SUMMARY")
    print("=" * 55)

    print("Source records:", len(records))
    print("Accepted jobs:", len(extracted))
    print("Rejected entries:", len(rejected))
    print("Usage records:", len(usage_rows))
    print("Cache hits:", cache_hits)
    print("Source records requiring API:", api_requests)
    print("Cache misses skipped:", cache_misses_skipped)
    print("Processing errors:", len(processing_errors))

    print("\nOutput:", OUTPUT_FILE)
    print("Rejected:", REJECTED_FILE)
    print("Usage:", USAGE_FILE)
    print("Errors:", ERROR_FILE)

    return {
        "source_records": len(records),
        "accepted_jobs": len(extracted),
        "rejected_entries": len(rejected),
        "usage_records": len(usage_rows),
        "cache_hits": cache_hits,
        "api_requests": api_requests,
        "cache_misses_skipped": cache_misses_skipped,
        "processing_errors": len(processing_errors),
    }


# ---------------------------------------------------------
# COMMAND LINE ENTRY POINT
# ---------------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description="Batch Gemini job extraction"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="Maximum source records; 0 means all"
    )

    parser.add_argument(
        "--cache-only",
        action="store_true",
        help="Use cached Gemini results only"
    )

    parser.add_argument(
        "--max-api-requests",
        type=int,
        default=None,
        help="Maximum source records sent to Gemini"
    )

    parser.add_argument(
        "--priority",
        choices=[
            "all",
            "high_priority",
            "needs_review"
        ],
        default="all"
    )

    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Optional input JSONL file"
    )

    args = parser.parse_args()

    if args.limit < 0:
        parser.error("--limit must be >= 0")

    if (
        args.max_api_requests is not None
        and args.max_api_requests < 0
    ):
        parser.error("--max-api-requests must be >= 0")

    run(
        limit=None if args.limit == 0 else args.limit,
        cache_only=args.cache_only,
        max_api_requests=args.max_api_requests,
        priority=args.priority,
        input_path=args.input
    )


if __name__ == "__main__":
    main()
