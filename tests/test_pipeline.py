
import json
import sqlite3

from pipeline.schemas import JobExtraction, ExtractionResult
from pipeline.deduplication import deduplicate
from pipeline.database import (
    CREATE_TABLE_SQL,
    UPSERT_SQL,
    record_to_values,
)


def sample_record(source_id="123", title="Data Engineer"):
    return {
        "job_key": "test-key-" + source_id,
        "source": "greenhouse",
        "source_id": source_id,
        "source_url": f"https://example.com/jobs/{source_id}",
        "source_record_key": "source-" + source_id,
        "data": {
            "company": "Example",
            "title": title,
            "city": "San Francisco",
            "country": "US",
            "skills": ["Python", "SQL"],
            "evidence": {"title": title},
        },
        "warnings": [],
    }


def test_visa_sponsorship_boolean():
    job = JobExtraction(
        company="Example",
        title="Data Engineer",
        visa_sponsorship=False,
    )
    assert job.visa_sponsorship == "no"


def test_evidence_normalization():
    result = ExtractionResult.model_validate({
        "jobs": [{
            "company": "Example",
            "title": "Data Engineer",
            "evidence": {
                "skills": ["Python", "SQL"],
                "employment_type": None,
            },
        }]
    })

    evidence = result.jobs[0].evidence
    assert evidence["skills"] == "Python | SQL"
    assert evidence["employment_type"] == ""


def test_deduplication():
    records = [
        sample_record("123"),
        sample_record("456"),
        sample_record("789", "ML Engineer"),
    ]

    unique, duplicates = deduplicate(records)

    assert len(unique) == 2
    assert len(duplicates) == 1


def test_sqlite_upsert():
    connection = sqlite3.connect(":memory:")
    connection.execute(CREATE_TABLE_SQL)

    record = sample_record()

    connection.execute(
        UPSERT_SQL,
        record_to_values(record),
    )

    connection.execute(
        UPSERT_SQL,
        record_to_values(record),
    )

    count = connection.execute(
        "SELECT COUNT(*) FROM jobs"
    ).fetchone()[0]

    assert count == 1

    stored = connection.execute(
        "SELECT skills_json FROM jobs"
    ).fetchone()[0]

    assert json.loads(stored) == ["Python", "SQL"]

    connection.close()
