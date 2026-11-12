
# Twig Take-Home - Deliverable 1
## Job Scraping and Processing Pipeline

## 1. Project Overview

This project implements a Python-based pipeline for collecting,
filtering, extracting, validating, deduplicating, and storing
publicly available job postings.

The pipeline focuses on US-based and US-remote opportunities
in data analytics, data science, machine learning, AI, and
data/platform engineering.

The workflow includes:

1. Public job-source scraping
2. Raw HTTP response caching
3. Candidate prefiltering
4. Gemini-based structured extraction
5. Pydantic schema validation
6. Location and job relevance filtering
7. Evidence auditing
8. Token usage and extraction caching
9. Job deduplication
10. SQLite database storage
11. Automated testing and data-quality checks

The scraping component is the core of Deliverable 1.
Additional processing stages extend the implementation.

## 2. Data Sources

### 2.1 Greenhouse

The pipeline collects public job postings using
Greenhouse job-board endpoints.

Configured companies include:

- Stripe
- Airbnb
- Databricks
- Figma

### 2.2 Lever

The pipeline uses publicly accessible Lever
job-posting endpoints.

Configured companies include:

- Palantir
- Plaid

Individual endpoints may be unavailable or return errors.
The scraper logs source failures without necessarily
stopping the entire pipeline.

### 2.3 Hacker News

The pipeline collects candidate job postings from the
monthly "Ask HN: Who is hiring?" discussion.

A single comment may contain multiple positions.
Relevant comments are retained for downstream processing.

### Data Source Distribution

The final SQLite dataset contains:

| Source | Stored Jobs |
|---|---:|
| Greenhouse | 21 |
| Hacker News | 6 |
| Lever | 3 |
| **Total** | **30** |

Public scraping endpoints do not require authentication.
Applicable source policies and robots.txt requirements
must be respected.

## 3. Technology Stack

| Component | Technology |
|---|---|
| Programming language | Python 3.12 |
| Public job collection | HTTP APIs and HTML parsing |
| Structured extraction | Google Gemini |
| Data validation | Pydantic |
| Local database | SQLite |
| Structured output | JSONL |
| Automated testing | pytest |
| Environment configuration | python-dotenv / .env |
| Development environment | VS Code |
| Version control | Git |

The extraction implementation uses a Gemini model
configured in the pipeline.

## 4. Project Structure

```text
twig_deliverable1/
|
|-- pipeline/
|   |-- __init__.py
|   |-- config.py
|   |-- scraper_utils.py
|   |-- greenhouse.py
|   |-- lever.py
|   |-- hackernews.py
|   |-- filters.py
|   |-- candidate_prefilter.py
|   |-- main.py
|   |-- schemas.py
|   |-- extractor.py
|   |-- validator.py
|   |-- batch_extractor.py
|   |-- deduplication.py
|   |-- database.py
|   |-- cost_tracker.py
|   |-- evidence_audit.py
|   |-- logging_config.py
|
|-- tests/
|   |-- test_candidate_prefilter.py
|   |-- test_filters.py
|   |-- test_pipeline.py
|   |-- test_robots.py
|
|-- data/
|   |-- scraped_jobs.jsonl
|   |-- prefiltered_jobs.jsonl
|   |-- extracted_jobs.jsonl
|   |-- rejected_jobs.jsonl
|   |-- deduplicated_jobs.jsonl
|   |-- duplicate_jobs.jsonl
|   |-- llm_usage.jsonl
|   |-- cost_report.json
|   |-- evidence_audit.jsonl
|   |-- twig_jobs.db
|   |-- raw/
|   |-- extraction_cache/
|
|-- logs/
|-- requirements.txt
|-- .env.example
|-- .gitignore
|-- Makefile
|-- README_DELIVERABLE_1.md
```

Some output files and cache directories are generated
during execution.

## 5. Installation and Setup

### Step 1: Create a virtual environment

```bash
python -m venv venv
```

### Step 2: Activate the environment

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source venv/bin/activate
```

### Step 3: Install dependencies

```bash
python -m pip install -r requirements.txt
```

### Step 4: Configure environment variables

Copy the example configuration:

Windows:

```powershell
Copy-Item .env.example .env
```

macOS/Linux:

```bash
cp .env.example .env
```

Configure the required Gemini API credentials
according to pipeline/config.py.

The scraping stage does not require a Gemini API key.

Never commit actual API keys or the .env file.

## 6. Run the Job Scraper

Execute the scraper from the project root:

```bash
python -m pipeline.main
```

Alternatively, where Make is available:

```bash
make run
```

The scraper collects candidate postings from
Greenhouse, Lever, and Hacker News.

Primary output:

```text
data/scraped_jobs.jsonl
```

Raw HTTP responses may be cached under:

```text
data/raw/
```

Each source record retains available source identifiers,
URLs, raw job content, and collection metadata.

## 7. Candidate Prefiltering

The prefiltering stage identifies potentially relevant
job postings before expensive LLM extraction.

It prioritizes opportunities associated with:

- Data analytics
- Data science
- Machine learning
- Artificial intelligence
- Data engineering
- Relevant platform and infrastructure engineering

Candidate records are categorized by priority.

Observed candidate counts:

| Metric | Count |
|---|---:|
| Prefiltered candidate rows | 587 |
| High-priority rows | 390 |
| Needs-review rows | 197 |
| Unique extraction candidates | 290 |

The prefiltered JSONL file contains repeated source
identities from collection history.

The batch extraction loader deduplicates source
identities before processing.

Primary output:

```text
data/prefiltered_jobs.jsonl
```

## 8. Gemini-Based Structured Extraction

Google Gemini converts unstructured job descriptions
into structured job information.

Extracted fields may include:

- Company name
- Job title
- Seniority
- City and country
- Remote policy
- Salary range and currency
- Employment type
- Required skills
- Visa sponsorship information
- Posted date
- Supporting evidence

Missing or unsupported information should remain
unknown rather than being fabricated.

### Run a Small Batch

```bash
python -m pipeline.batch_extractor --limit 10
```

### Process All Available Candidates

```bash
python -m pipeline.batch_extractor --limit 0
```

### Rebuild Outputs from Existing Cache Only

```bash
python -m pipeline.batch_extractor --limit 0 --cache-only
```

The cache-only command avoids new Gemini API requests
and uses available cached extraction results.

### Limit New API Requests

```bash
python -m pipeline.batch_extractor --limit 0 --max-api-requests 5
```

### Extraction Outputs

```text
data/extracted_jobs.jsonl
data/rejected_jobs.jsonl
data/llm_usage.jsonl
```

Extraction results are cached using source identity,
source content, and extraction configuration.

Important: Running the batch extractor can rewrite
the extraction output files. Back up important
results before performing limited experiments.

### Latest Extraction Results

| Metric | Count |
|---|---:|
| Unique extraction candidates | 290 |
| Candidates with cached results | 127 |
| Accepted extracted jobs | 31 |
| Rejected extraction entries | 106 |
| Candidates without cached results | 163 |
| Processing errors | 0 |

The extraction stage is partially complete.

127 of 290 unique source candidates have cached
extraction results.

The remaining 163 candidates have not yet been
processed by Gemini.

## 9. Validation and Evidence Auditing

Structured extraction results are validated using
Pydantic schemas and source-text checks.

Validation includes:

- Relevant job titles
- US location eligibility
- Remote-work eligibility
- Schema compatibility
- Missing required fields
- Supporting evidence
- Unsupported or ambiguous extracted values

Rejected records are retained for inspection.

Run evidence auditing:

```bash
python -m pipeline.evidence_audit
```

Evidence audit output:

```text
data/evidence_audit.jsonl
```

Evidence checks help identify unsupported claims,
but do not guarantee that every extracted value
is factually correct.

## 10. Token Usage and Cost Tracking

The pipeline records Gemini extraction usage.

Tracked information includes:

- Model name
- Input tokens
- Output tokens
- Total tokens
- Cached processing
- New API requests

Run the cost tracker:

```bash
python -m pipeline.cost_tracker
```

Output:

```text
data/cost_report.json
```

USD cost estimates depend on correctly configured
model pricing.

When pricing is unavailable, cost values should
remain unknown rather than being invented.

## 11. Job Deduplication

Deduplication identifies repeated job postings using
normalized job attributes.

Matching attributes include:

- Company name
- Job title
- City
- Country
- Source identifiers

Run:

```bash
python -m pipeline.deduplication
```

Outputs:

```text
data/deduplicated_jobs.jsonl
data/duplicate_jobs.jsonl
```

### Verified Deduplication Results

| Metric | Count |
|---|---:|
| Input accepted jobs | 31 |
| Unique jobs | 30 |
| Duplicates removed | 1 |

### Duplicate Identified

Company: Airbnb

Position: Senior Machine Learning Engineer, Trust

Location: San Francisco

Reason:

```text
matching_company_title_location
```

The implementation uses conservative normalized
matching.

Distinct requisitions sharing the same company,
title, and location may require manual review.

## 12. SQLite Database

The deduplicated dataset is stored in SQLite.

Run:

```bash
python -m pipeline.database
```

Database file:

```text
data/twig_jobs.db
```

The database stores structured job fields,
source identifiers, URLs, evidence, and
validation-related information.

The implementation supports upsert behavior
to prevent repeated imports from creating
duplicate records for the same job key.

### Verified Database Results

| Check | Result |
|---|---|
| Input unique jobs | 30 |
| Total stored jobs | 30 |
| SQLite integrity | OK |

### Source Distribution

| Source | Count |
|---|---:|
| Greenhouse | 21 |
| Hacker News | 6 |
| Lever | 3 |
| **Total** | **30** |

### Database Integrity Verification

```python
import sqlite3

conn = sqlite3.connect("data/twig_jobs.db")

count = conn.execute(
    "SELECT COUNT(*) FROM jobs"
).fetchone()[0]

integrity = conn.execute(
    "PRAGMA integrity_check"
).fetchone()[0]

print("Total jobs:", count)
print("Database integrity:", integrity)

conn.close()
```

Verified output:

```text
Total jobs: 30
Database integrity: ok
```

## 13. Data Quality

The pipeline includes validation of required fields,
structured values, and supporting evidence.

Quality checks are intended to identify:

- Missing company names
- Missing job titles
- Invalid location values
- Missing source URLs
- Invalid structured skills
- Missing evidence
- Unsupported extracted fields

The current database has passed its SQLite
integrity check.

A separate final field-level quality audit should
be performed before claiming zero missing values
across every required field.

## 14. Automated Testing

Automated tests are implemented using pytest.

Run:

```bash
python -m pytest tests -v
```

The test suite covers areas including:

- Candidate prefiltering
- Job relevance filtering
- US location eligibility
- Hacker News filtering
- Structured validation
- Deduplication
- SQLite behavior
- Robots.txt-related behavior

### Latest Test Results

```text
20 passed
```

All 20 automated tests passed in the latest
reported local execution.

Passing tests verify the implemented test cases;
they do not guarantee complete production coverage.

## 15. Reliability and Reproducibility

The pipeline includes:

1. HTTP response caching
2. Source-level failure isolation
3. Network retry handling
4. Candidate prefiltering
5. Stable source identity deduplication
6. Gemini extraction caching
7. Pydantic schema validation
8. Rejected-record tracking
9. Token usage logging
10. Evidence auditing
11. Job-level deduplication
12. SQLite upsert behavior
13. Automated testing

These mechanisms reduce unnecessary API calls
and support repeatable processing.

## 16. Known Limitations

### 16.1 Partial Extraction Coverage

Only 127 of 290 unique candidates have cached
extraction results.

163 candidates remain unprocessed.

### 16.2 API Quotas

Gemini API rate limits may interrupt extraction
of uncached candidates.

The extraction cache helps avoid repeated
successful API requests.

### 16.3 LLM Accuracy

LLM extraction may omit fields or produce
unsupported values.

Schema validation and evidence auditing reduce
this risk but cannot eliminate it.

### 16.4 Location Ambiguity

Remote, hybrid, multi-city, and ambiguous
location descriptions may require manual review.

### 16.5 Deduplication

Normalized company/title/location matching
may miss near-duplicates or merge distinct
job requisitions.

### 16.6 Hacker News Parsing

Changes to discussion structure, pagination,
or HTML markup may require scraper updates.

### 16.7 Source Availability

Public job-board endpoints may return errors,
including HTTP 404 responses.

Individual source failures should be logged
and handled without unnecessary pipeline failure.

### 16.8 Scraping Compliance

Robots.txt handling and compliance with
applicable source terms should be verified
before production deployment.

### 16.9 Dataset Scope

The collected records represent a candidate
sample and should not be interpreted as a
complete inventory of US job opportunities.

## 17. Observed Pipeline Summary

The latest verified processing results are:

| Pipeline Stage | Result |
|---|---:|
| Prefiltered candidate rows | 587 |
| Unique extraction candidates | 290 |
| Cached extraction results | 127 |
| Accepted extracted jobs | 31 |
| Rejected extraction entries | 106 |
| Remaining uncached candidates | 163 |
| Deduplicated jobs | 30 |
| SQLite stored jobs | 30 |
| Automated tests passed | 20 |
| SQLite integrity | OK |

The 587 prefiltered rows contain repeated
source identities.

The extraction loader reduces these to
290 unique candidate identities.

The latest available cached results cover
127 of those candidates.

After validation, 31 jobs were accepted.
Deduplication removed one duplicate, leaving
30 unique jobs stored in SQLite.

## 18. Security and Submission

The following files should not be included
in a public repository:

- .env containing API credentials
- Virtual environment directories
- Python bytecode and cache folders
- Private extraction caches
- Temporary development backups
- Sensitive logs
- Local IDE configuration containing secrets

The .env.example file may be included when
it contains only placeholder values.

The .gitignore file excludes development
artifacts and sensitive configuration.

Submission artifacts should include sufficient
code, documentation, tests, and permitted sample
outputs for reproducibility.

## 19. Conclusion

Twig Deliverable 1 provides a functional
public-source job scraping and processing pipeline.

The implementation integrates:

- Greenhouse, Lever, and Hacker News scraping
- Candidate prefiltering
- Gemini-based structured extraction
- Pydantic validation
- Evidence auditing
- Token usage tracking
- Extraction caching
- Job deduplication
- SQLite database storage
- Automated testing

The latest verified run produced:

- 31 accepted extracted jobs
- 30 unique jobs after deduplication
- 30 jobs stored in SQLite
- 20 passing automated tests
- Successful SQLite integrity verification

Gemini extraction currently covers 127 of
290 unique candidates.

The remaining 163 candidates can be processed
in additional batches, subject to API quotas.

The project demonstrates an end-to-end workflow
for collecting and processing public job data,
with documented limitations and reproducible
local execution steps.
