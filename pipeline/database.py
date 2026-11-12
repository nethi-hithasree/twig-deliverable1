
"""
Twig Deliverable 1 - SQLite Database Storage

Loads deduplicated job postings into SQLite.

Input:
    data/deduplicated_jobs.jsonl

Output:
    data/twig_jobs.db

Features:
- Persistent SQLite storage
- Unique job keys
- Idempotent inserts and updates
- Source provenance
- Evidence and warnings preservation
- Data integrity checks
"""

import json
import sqlite3

from datetime import datetime, timezone

from .config import ROOT


DATA_DIR = ROOT / "data"

INPUT_FILE = DATA_DIR / "deduplicated_jobs.jsonl"
DATABASE_FILE = DATA_DIR / "twig_jobs.db"


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    job_key TEXT PRIMARY KEY,

    company TEXT,
    title TEXT,
    seniority TEXT,

    city TEXT,
    country TEXT,
    remote_policy TEXT,

    salary_min REAL,
    salary_max REAL,
    currency TEXT,

    employment_type TEXT,
    skills_json TEXT,

    visa_sponsorship TEXT,
    posted_date TEXT,

    source TEXT,
    source_id TEXT,
    source_url TEXT,
    source_record_key TEXT,

    evidence_json TEXT,
    warnings_json TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


CREATE_INDEX_SQL = [
    """
    CREATE INDEX IF NOT EXISTS idx_jobs_company
    ON jobs(company);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_jobs_title
    ON jobs(title);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_jobs_city
    ON jobs(city);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_jobs_source
    ON jobs(source);
    """,
]


UPSERT_SQL = """
INSERT INTO jobs (
    job_key,
    company,
    title,
    seniority,
    city,
    country,
    remote_policy,
    salary_min,
    salary_max,
    currency,
    employment_type,
    skills_json,
    visa_sponsorship,
    posted_date,
    source,
    source_id,
    source_url,
    source_record_key,
    evidence_json,
    warnings_json,
    created_at,
    updated_at
)
VALUES (
    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
)
ON CONFLICT(job_key) DO UPDATE SET
    company = excluded.company,
    title = excluded.title,
    seniority = excluded.seniority,
    city = excluded.city,
    country = excluded.country,
    remote_policy = excluded.remote_policy,
    salary_min = excluded.salary_min,
    salary_max = excluded.salary_max,
    currency = excluded.currency,
    employment_type = excluded.employment_type,
    skills_json = excluded.skills_json,
    visa_sponsorship = excluded.visa_sponsorship,
    posted_date = excluded.posted_date,
    source = excluded.source,
    source_id = excluded.source_id,
    source_url = excluded.source_url,
    source_record_key = excluded.source_record_key,
    evidence_json = excluded.evidence_json,
    warnings_json = excluded.warnings_json,
    updated_at = excluded.updated_at;
"""




CREATE_CHANGE_HISTORY_SQL = """
CREATE TABLE IF NOT EXISTS job_change_history (
    change_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_key TEXT NOT NULL,
    field_name TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_key) REFERENCES jobs(job_key)
);
"""

TRACKED_FIELDS = (
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
    "skills_json",
    "visa_sponsorship",
    "posted_date"
)


def create_change_history(connection):
    connection.execute(CREATE_CHANGE_HISTORY_SQL)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_change_history_job
        ON job_change_history(job_key, changed_at)
    """)

    for field in TRACKED_FIELDS:
        connection.execute(f"""
            CREATE TRIGGER IF NOT EXISTS track_job_{field}
            AFTER UPDATE OF {field} ON jobs
            WHEN OLD.{field} IS NOT NEW.{field}
            BEGIN
                INSERT INTO job_change_history (
                    job_key,
                    field_name,
                    old_value,
                    new_value
                )
                VALUES (
                    NEW.job_key,
                    '{field}',
                    CAST(OLD.{field} AS TEXT),
                    CAST(NEW.{field} AS TEXT)
                );
            END;
        """)


def utc_now():
    return datetime.now(
        timezone.utc
    ).isoformat()


def load_jobs():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Missing deduplicated jobs file: {INPUT_FILE}"
        )

    records = []

    with INPUT_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:

        for line_number, line in enumerate(
            file,
            start=1
        ):
            if not line.strip():
                continue

            record = json.loads(line)

            if not record.get("job_key"):
                raise ValueError(
                    f"Missing job_key on line {line_number}"
                )

            if not isinstance(
                record.get("data"),
                dict
            ):
                raise ValueError(
                    f"Invalid job data on line {line_number}"
                )

            records.append(record)

    return records


def create_database(connection):
    connection.execute(CREATE_TABLE_SQL)

    for statement in CREATE_INDEX_SQL:
        connection.execute(statement)

    create_change_history(connection)


def record_to_values(record):
    job = record["data"]
    timestamp = utc_now()

    return (
        record["job_key"],

        job.get("company"),
        job.get("title"),
        job.get("seniority"),

        job.get("city"),
        job.get("country"),
        job.get("remote_policy"),

        job.get("salary_min"),
        job.get("salary_max"),
        job.get("currency"),

        job.get("employment_type"),

        json.dumps(
            job.get("skills") or [],
            ensure_ascii=False
        ),

        job.get("visa_sponsorship"),
        job.get("posted_date"),

        record.get("source"),
        record.get("source_id"),
        record.get("source_url"),
        record.get("source_record_key"),

        json.dumps(
            job.get("evidence") or {},
            ensure_ascii=False
        ),

        json.dumps(
            record.get("warnings") or [],
            ensure_ascii=False
        ),

        timestamp,
        timestamp,
    )


def save_jobs(connection, records):
    for record in records:
        connection.execute(
            UPSERT_SQL,
            record_to_values(record)
        )


def print_summary(connection, input_count):
    cursor = connection.cursor()

    total = cursor.execute(
        "SELECT COUNT(*) FROM jobs"
    ).fetchone()[0]

    print("\n" + "=" * 55)
    print("SQLITE DATABASE SUMMARY")
    print("=" * 55)

    print("Input unique jobs:", input_count)
    print("Jobs stored:", total)

    print("\nSOURCE DISTRIBUTION")

    rows = cursor.execute(
        """
        SELECT source, COUNT(*)
        FROM jobs
        GROUP BY source
        ORDER BY COUNT(*) DESC
        """
    ).fetchall()

    for source, count in rows:
        print(f"{source}: {count}")

    print("\nSAMPLE JOBS")

    rows = cursor.execute(
        """
        SELECT company, title, city, source
        FROM jobs
        ORDER BY company, title
        LIMIT 10
        """
    ).fetchall()

    for company, title, city, source in rows:
        print(
            f"{company} | {title} | "
            f"{city} | {source}"
        )

    print("\nDATABASE:", DATABASE_FILE)


def run():
    records = load_jobs()

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    with sqlite3.connect(
        DATABASE_FILE
    ) as connection:

        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        create_database(connection)

        save_jobs(
            connection,
            records
        )

        connection.commit()

        integrity = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        if integrity != "ok":
            raise RuntimeError(
                f"SQLite integrity check failed: {integrity}"
            )

        print_summary(
            connection,
            len(records)
        )


if __name__ == "__main__":
    run()
