
import json
import re
from pathlib import Path

from .config import ROOT
from .extractor import clean_description

DATA_DIR = ROOT / "data"

RAW_FILE = DATA_DIR / "scraped_jobs.jsonl"
EXTRACTED_FILE = DATA_DIR / "extracted_jobs.jsonl"
AUDIT_FILE = DATA_DIR / "evidence_audit.jsonl"

FIELDS_TO_CHECK = [
    "company",
    "title",
    "seniority",
    "city",
    "country",
    "remote_policy",
    "salary_min",
    "salary_max",
    "currency",
    "employment_type",
    "visa_sponsorship",
    "posted_date",
]


def load_jsonl(path):
    if not path.exists():
        raise FileNotFoundError(path)

    with path.open("r", encoding="utf-8") as file:
        return [
            json.loads(line)
            for line in file
            if line.strip()
        ]


def normalize_text(text):
    return re.sub(
        r"\s+",
        " ",
        str(text or "")
    ).strip().casefold()


def audit():
    raw_records = load_jsonl(RAW_FILE)
    extracted_records = load_jsonl(EXTRACTED_FILE)

    # Match records by source identity.
    from .batch_extractor import record_key

    raw_by_key = {
        record_key(record): record
        for record in raw_records
    }

    results = []

    for row in extracted_records:
        raw = raw_by_key.get(
            row["source_record_key"]
        )

        if raw is None:
            results.append({
                "source_record_key": row["source_record_key"],
                "status": "missing_source",
            })
            continue

        source_text = "\n".join([
            f"Company: {raw.get('company_raw') or ''}",
            f"Title: {raw.get('title_raw') or ''}",
            f"Location: {raw.get('location_raw') or ''}",
            "Description: " + clean_description(
                raw.get("description_raw", "")
            ),
        ])[:20000]

        job = row["data"]
        evidence = job.get("evidence") or {}

        issues = []

        for field in FIELDS_TO_CHECK:
            value = job.get(field)

            if value is None:
                continue

            snippet = evidence.get(field)

            if not isinstance(snippet, str) or not snippet.strip():
                issues.append({
                    "field": field,
                    "issue": "missing_evidence",
                    "value": value,
                })
                continue

            if normalize_text(snippet) not in normalize_text(source_text):
                issues.append({
                    "field": field,
                    "issue": "snippet_not_found",
                    "value": value,
                    "snippet": snippet,
                })

        # Check whether extracted skills appear in the source.
        for skill in job.get("skills") or []:
            if normalize_text(skill) not in normalize_text(source_text):
                issues.append({
                    "field": "skills",
                    "issue": "skill_not_found",
                    "value": skill,
                })

        results.append({
            "source_record_key": row["source_record_key"],
            "title": job.get("title"),
            "status": (
                "review_required" if issues else "text_checks_passed"
            ),
            "issues": issues,
            "validation_warnings": row.get("warnings", []),
        })

    with AUDIT_FILE.open("w", encoding="utf-8") as file:
        for result in results:
            file.write(
                json.dumps(result, ensure_ascii=False) + "\n"
            )

    review_count = sum(
        result["status"] != "text_checks_passed"
        for result in results
    )

    print("\nEVIDENCE AUDIT SUMMARY")
    print("=" * 45)
    print("Accepted jobs audited:", len(results))
    print("Records requiring evidence review:", review_count)
    print("Audit saved to:", AUDIT_FILE)


if __name__ == "__main__":
    audit()
