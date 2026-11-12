import csv
import json
from collections import Counter
from pathlib import Path

DATA = Path("data")
FIELDS = [
    "company", "title", "seniority", "city", "country",
    "remote_policy", "salary_min", "salary_max", "currency",
    "employment_type", "visa_sponsorship", "posted_date"
]

def normalize(value, field):
    if value is None:
        return ""
    value = str(value).strip().lower()
    if value in ("none", "null", "nan", "not specified", "unknown"):
        return ""
    value = " ".join(value.split())
    if field in ("salary_min", "salary_max") and value:
        try:
            return str(float(value.replace(",", "").replace("$", "")))
        except ValueError:
            pass
    if field == "country" and value in ("united states", "united states of america", "usa"):
        return "us"
    if field == "employment_type" and value == "intern":
        return "internship"
    return value

def load_jsonl(filename):
    path = DATA / filename
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

with (DATA / "evaluation_20_template.csv").open(
    encoding="utf-8-sig", newline=""
) as f:
    evaluations = list(csv.DictReader(f))

if len(evaluations) != 20 or any(
    r["labeling_status"].strip().lower() not in ("completed", "complete", "done")
    for r in evaluations
):
    raise RuntimeError("Expected exactly 20 completed manual evaluations")

accepted = load_jsonl("extracted_jobs.jsonl")
rejected = load_jsonl("rejected_jobs.jsonl")

predictions = {}
statuses = {}

for status, records in [("rejected", rejected), ("accepted", accepted)]:
    for record in records:
        key = (
            str(record.get("source", "")).strip().lower(),
            str(record.get("source_id", "")).strip()
        )
        predictions[key] = record.get("data") or {}
        statuses[key] = status

details = []
counts = Counter()
field_correct = Counter()
field_total = Counter()

for row in evaluations:
    key = (
        row["source"].strip().lower(),
        row["source_id"].strip()
    )
    predicted = predictions.get(key, {})
    status = statuses.get(key, "not_extracted")
    counts[status] += 1

    for field in FIELDS:
        gold = normalize(row.get("gold_" + field), field)
        prediction = normalize(predicted.get(field), field)
        correct = gold == prediction

        field_total[field] += 1
        field_correct[field] += int(correct)

        details.append({
            "evaluation_id": row["evaluation_id"],
            "source": row["source"],
            "source_id": row["source_id"],
            "processing_status": status,
            "field": field,
            "gold_value": gold,
            "predicted_value": prediction,
            "correct": correct
        })

with (DATA / "evaluation_accuracy.csv").open(
    "w", encoding="utf-8", newline=""
) as f:
    writer = csv.DictWriter(f, fieldnames=list(details[0]))
    writer.writeheader()
    writer.writerows(details)

total = sum(field_total.values())
correct = sum(field_correct.values())

summary = {
    "labeled_postings": len(evaluations),
    "hackernews_postings": sum(
        r["source"].strip().lower() == "hackernews"
        for r in evaluations
    ),
    "coverage": dict(counts),
    "overall_field_accuracy": round(correct / total, 4),
    "field_accuracy": {
        field: round(field_correct[field] / field_total[field], 4)
        for field in FIELDS
    },
    "methodology": (
        "Exact-match comparison after limited normalization. "
        "Accepted and rejected extraction records are both evaluated. "
        "Missing predictions are treated as empty. "
        "Empty gold values represent information not specified. "
        "Skills excluded. This measures field agreement across all "
        "20 labeled postings, not end-to-end accepted-job accuracy."
    )
}

(DATA / "evaluation_summary.json").write_text(
    json.dumps(summary, indent=2) + "\n",
    encoding="utf-8"
)

print("SUCCESS: Final evaluation generated")
print("Labeled postings:", len(evaluations))
print("Hacker News:", summary["hackernews_postings"])
print("Processing coverage:", dict(counts))
print("Overall field accuracy:", f"{100 * correct / total:.2f}%")
print("Detailed comparisons:", len(details))
