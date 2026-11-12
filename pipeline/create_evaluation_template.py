
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

INPUT = DATA / "prefiltered_jobs.jsonl"
OUTPUT = DATA / "evaluation_20_template.csv"

LABEL_FIELDS = [
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
    "skills",
    "visa_sponsorship",
    "posted_date",
]

def load_jsonl(path):
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                yield json.loads(line)

def record_identity(record):
    source = str(record.get("source") or "")
    source_id = str(record.get("source_id") or "")
    url = str(record.get("source_url") or "")

    raw = json.dumps(
        [source, source_id, url],
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()

def select_unique(records):
    unique = {}

    for record in records:
        key = record_identity(record)
        unique.setdefault(key, record)

    return list(unique.values())

def main():
    records = select_unique(load_jsonl(INPUT))

    hn = [
        record for record in records
        if record.get("source") == "hackernews"
    ]

    other = [
        record for record in records
        if record.get("source") in ("greenhouse", "lever")
    ]

    hn.sort(
        key=lambda r: (
            r.get("prefilter_priority") != "high_priority",
            str(r.get("source_id") or ""),
        )
    )

    other.sort(
        key=lambda r: (
            r.get("prefilter_priority") != "high_priority",
            str(r.get("source") or ""),
            str(r.get("source_id") or ""),
        )
    )

    if len(hn) < 10 or len(other) < 10:
        raise RuntimeError(
            f"Insufficient unique records: "
            f"HN={len(hn)}, other={len(other)}"
        )

    selected = hn[:10] + other[:10]

    columns = [
        "evaluation_id",
        "source",
        "source_id",
        "source_url",
        "title_raw",
        "company_raw",
        "location_raw",
        "description_raw",
        "prefilter_priority",
        "labeling_status",
        "labeling_notes",
    ]

    columns += [
        "gold_" + field for field in LABEL_FIELDS
    ]

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=columns,
        )

        writer.writeheader()

        for index, record in enumerate(
            selected, start=1
        ):
            row = {
                "evaluation_id": f"EVAL-{index:02d}",
                "source": record.get("source", ""),
                "source_id": record.get("source_id", ""),
                "source_url": record.get("source_url", ""),
                "title_raw": record.get("title_raw", ""),
                "company_raw": record.get("company_raw", ""),
                "location_raw": record.get("location_raw", ""),
                "description_raw": record.get(
                    "description_raw", ""
                ),
                "prefilter_priority": record.get(
                    "prefilter_priority", ""
                ),
                "labeling_status": "pending",
                "labeling_notes": "",
            }

            for field in LABEL_FIELDS:
                row["gold_" + field] = ""

            writer.writerow(row)

    print("Evaluation template created:", OUTPUT)
    print("Total selected:", len(selected))
    print("Hacker News selected:", 10)
    print("Greenhouse/Lever selected:", 10)
    print("Ground-truth labels: pending manual review")

if __name__ == "__main__":
    main()
