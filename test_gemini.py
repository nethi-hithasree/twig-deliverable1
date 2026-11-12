
import json
from pathlib import Path

from pipeline.extractor import extract_jobs
from pipeline.filters import is_relevant_title

data_path = Path("data/scraped_jobs.jsonl")

if not data_path.exists():
    raise FileNotFoundError(
        "Run the scraper first to generate scraped_jobs.jsonl"
    )

# Load collected job postings
with data_path.open("r", encoding="utf-8") as file:
    records = [
        json.loads(line)
        for line in file
        if line.strip()
    ]

# Select a posting with a relevant engineering title
record = next(
    (
        job for job in records
        if job.get("source") in ("greenhouse", "lever")
        and is_relevant_title(job.get("title_raw", ""))
        and job.get("description_raw")
    ),
    None,
)

if record is None:
    raise RuntimeError(
        "No suitable engineering job found for testing."
    )

print("=" * 50)
print("TESTING GEMINI EXTRACTION")
print("=" * 50)

print("Source:", record.get("source"))
print("Company:", record.get("company_raw"))
print("Original title:", record.get("title_raw"))
print("Location:", record.get("location_raw"))

print("\nDESCRIPTION PREVIEW:")
print(str(record.get("description_raw", ""))[:500])

print("\nSending posting to Gemini...")

result, usage = extract_jobs(record)

print("\nEXTRACTED JOBS:")
print(result.model_dump_json(indent=2))

print("\nTOKEN USAGE:")
print(json.dumps(usage, indent=2))

# Save the result so we can inspect it without
# making another Gemini API request.
output_path = Path("data/extraction_test_result.json")

output_path.write_text(
    json.dumps(
        {
            "source": record.get("source"),
            "original_title": record.get("title_raw"),
            "extracted_jobs": result.model_dump(mode="json"),
            "usage": usage,
        },
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)

print("\nResult saved to:", output_path)
