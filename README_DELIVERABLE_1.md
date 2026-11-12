# Twig Take-Home – Deliverable 1: Scraping and Job Processing Pipeline

## 1. Project Overview

This project collects candidate job postings from public sources and processes them into a structured, validated, deduplicated SQLite dataset.

The pipeline supports data, machine learning, analytics, and platform engineering roles, with a focus on US and US-remote opportunities.

The workflow includes:

1. Public job-source scraping
2. Raw response caching
3. LLM-based structured extraction
4. Schema and location validation
5. Evidence auditing
6. Token usage tracking and extraction caching
7. Job deduplication
8. SQLite database storage
9. Automated testing and data-quality checks

The scraping component is Deliverable 1. Additional processing stages have been implemented as extensions.

## 2. Data Sources

### Greenhouse

Uses publicly accessible Greenhouse job-board endpoints.

Configured companies:

- Stripe
- Airbnb
- Databricks
- Figma

### Lever

Uses publicly accessible Lever postings endpoints.

Configured companies:

- Palantir
- Plaid

### Hacker News

Collects candidate postings from the current month's *Ask HN: Who is hiring?* thread.

The scraper follows available pagination and retains candidate comments for downstream extraction.

A single Hacker News comment may describe multiple positions.

No authentication is required to access the public scraping endpoints.

## 3. Technology Stack

| Component | Technology |
|---|---|
| Programming language | Python 3.12 |
| Public job collection | HTTP APIs and HTML parsing |
| Structured extraction | Google Gemini |
| Data validation | Pydantic |
| Local storage | SQLite |
| Structured files | JSONL |
| Automated testing | pytest |
| Environment configuration | `.env` |
| Development environment | VS Code |

The extraction implementation uses `gemini-3.5-flash-lite`.

## 4. Project Structure

```text
twig_deliverable1/
│
├── pipeline/
│   ├── __init__.py
│   ├── config.py
│   ├── scraper_utils.py
│   ├── greenhouse.py
│   ├── lever.py
│   ├── hackernews.py
│   ├── filters.py
│   ├── main.py
│   ├── schemas.py
│   ├── extractor.py
│   ├── validator.py
│   ├── batch_extractor.py
│   ├── deduplication.py
│   ├── database.py
│   ├── cost_tracker.py
│   └── evidence_audit.py
│
├── tests/
│   ├── test_filters.py
│   └── test_pipeline.py
│
├── data/
│   ├── scraped_jobs.jsonl
│   ├── extracted_jobs.jsonl
│   ├── rejected_jobs.jsonl
│   ├── deduplicated_jobs.jsonl
│   ├── duplicate_jobs.jsonl
│   ├── llm_usage.jsonl
│   ├── cost_report.json
│   ├── evidence_audit.jsonl
│   ├── twig_jobs.db
│   ├── raw/
│   └── extraction_cache/
│
├── logs/
├── requirements.txt
├── .env.example
├── .gitignore
├── Makefile
└── README_DELIVERABLE_1.md
```

Some output files and cache directories are generated at runtime.

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

Copy `.env.example` to `.env`.

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS/Linux:

```bash
cp .env.example .env
```

The public scraping stage does not require an API key.

Gemini-based extraction requires a valid Google Gemini API key configured according to `pipeline/config.py` and the local `.env` configuration.

Never commit API keys or the real `.env` file.

## 6. Run the Scraper

Execute from the project root:

```bash
python -m pipeline.main
```

Alternatively:

```bash
make run
```

The scraper collects candidate postings from Greenhouse, Lever, and Hacker News.

Output:

```text
data/scraped_jobs.jsonl
```

Raw HTTP responses are cached under:

```text
data/raw/
```

Each source record retains source information, raw job content, and collection metadata.

## 7. Structured Job Extraction

Gemini transforms raw source postings into structured job information.

Extracted fields include:

- Company
- Job title
- Seniority
- City and country
- Remote policy
- Salary range and currency
- Employment type
- Skills
- Visa sponsorship
- Posted date
- Supporting evidence

The extraction stage uses Pydantic schemas to validate the model response.

Run a small batch:

```bash
python -m pipeline.batch_extractor --limit 10
```

Process all available records:

```bash
python -m pipeline.batch_extractor --limit 0
```

Outputs:

```text
data/extracted_jobs.jsonl
data/rejected_jobs.jsonl
data/llm_usage.jsonl
```

Extraction results are cached to reduce repeated Gemini API requests.

The pipeline can reuse cached results when the source content and extraction configuration match.

## 8. Validation and Evidence

The validation layer checks structured extraction results against the original source text.

Validation includes:

- Job-title relevance
- US location requirements
- Location ambiguity
- Schema compatibility
- Supporting evidence
- Missing or unsupported values

Missing information is preserved as unknown rather than automatically fabricated.

Rejected records are retained for inspection.

The evidence-audit module can be executed using:

```bash
python -m pipeline.evidence_audit
```

Evidence auditing helps identify unsupported or missing evidence for extracted fields.

## 9. Token Usage and Cost Tracking

The extraction pipeline records token usage for Gemini processing.

Tracked information includes:

- Model name
- Input tokens
- Output tokens
- Total tokens
- Cache usage

Run:

```bash
python -m pipeline.cost_tracker
```

Output:

```text
data/cost_report.json
```

The cost tracker distinguishes cached processing from new API usage.

Estimated USD costs are reported only when model pricing is configured.

Otherwise, cost fields remain unknown rather than using unsupported estimates.

## 10. Deduplication

Deduplication compares normalized job attributes, including:

- Company
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

The implementation uses conservative normalized matching.

Potential duplicate requisitions should be reviewed when separate openings may share the same company, title, and location.

### Observed Results

| Metric | Count |
|---|---:|
| Extracted accepted jobs | 21 |
| Unique jobs after deduplication | 20 |
| Potential duplicates removed | 1 |

The detected duplicate candidate was an Airbnb Senior Machine Learning Engineer, Trust posting in San Francisco.

## 11. SQLite Database

The deduplicated dataset is stored in SQLite.

Run:

```bash
python -m pipeline.database
```

Output:

```text
data/twig_jobs.db
```

The database preserves structured job fields, source identifiers, source URLs, evidence, and validation warnings.

An upsert operation prevents duplicate rows for the same `job_key` during repeated imports.

### Database Verification

| Check | Result |
|---|---|
| Total stored jobs | 20 |
| Unique job keys | 20 |
| SQLite integrity | OK |

## 12. Data-Quality Results

The final stored dataset was checked for missing required information and malformed skills JSON.

| Quality check | Issues |
|---|---:|
| Missing company | 0 |
| Missing title | 0 |
| Missing city | 0 |
| Missing country | 0 |
| Missing source URL | 0 |
| Missing evidence | 0 |
| Invalid skills JSON | 0 |

These checks confirm structural completeness of the stored records. They do not independently establish that every extracted field is factually accurate.

## 13. Automated Testing

Tests use pytest.

Run:

```bash
python -m pytest tests -v
```

Implemented tests cover:

- Relevant job-title filtering
- US location and remote eligibility
- Hacker News candidate filtering
- Visa sponsorship normalization
- Evidence normalization
- Job deduplication
- SQLite upsert behavior

### Latest Test Results

```text
7 passed in 0.21s
```

All seven implemented automated tests passed in the latest local execution.

## 14. Reliability and Reproducibility

The pipeline includes several reliability mechanisms:

- HTTP response caching
- Per-domain request spacing
- Retry handling for network requests
- Source-level failure isolation
- Preservation of raw source records
- LLM extraction caching
- Schema validation
- Rejected-record tracking
- Token usage logging
- Stable deduplication fingerprints
- SQLite integrity verification

These mechanisms reduce unnecessary network requests and support debugging and repeatable local processing.

## 15. Known Limitations

1. **Robots.txt compliance:** Explicit robots.txt checking is not yet implemented. HTML scraping policy checks and applicable API terms must be verified before final submission or production use.

2. **Location extraction:** Multi-city, remote, and ambiguous location descriptions can require manual review.

3. **LLM accuracy:** Structured extraction may contain omissions or unsupported values. Evidence checks reduce this risk but do not eliminate it.

4. **API quotas:** Gemini free-tier rate limits can interrupt uncached extraction. Cached records can be reused without repeating successful calls.

5. **Deduplication:** Exact normalized company/title/location matching may miss near-duplicates or merge distinct requisitions with identical attributes.

6. **Hacker News parsing:** Changes to thread structure, pagination, or markup may require scraper updates.

7. **Cost reporting:** USD estimates require an explicit pricing configuration.

8. **Test coverage:** Seven automated tests pass, but broader integration testing and live-source validation are still recommended.

9. **Dataset scope:** The collected records are a candidate sample, not a comprehensive inventory of all available US jobs.

## 16. Observed Pipeline Summary

The latest full candidate dataset contained:

| Stage | Result |
|---|---:|
| Raw source candidate records | 102 |
| Accepted extracted jobs | 21 |
| Deduplicated jobs | 20 |
| SQLite stored jobs | 20 |
| Automated tests passed | 7 |

The 102 scraped candidates should not be interpreted as 102 unique jobs.

Rejected records include irrelevant roles, ambiguous or unsupported locations, extraction failures, and other validation outcomes.

## 17. Security and Submission

The following should not be included in a public repository or submission archive:

- `.env` containing API credentials
- Virtual environment folders
- Python bytecode and `__pycache__`
- Local IDE configuration containing secrets
- Temporary files and sensitive logs

The `.env.example` file may be included if it contains only placeholder values.

Submission artifacts should preserve sufficient documentation, code, test coverage, and permitted sample outputs to allow the reviewer to understand and reproduce the pipeline.

## 18. Conclusion

Twig Deliverable 1 provides a working public-source job collection pipeline, extended with structured Gemini extraction, schema validation, evidence checking, caching, deduplication, and SQLite storage.

The latest local run produced 20 deduplicated job records with complete core fields, passed SQLite integrity checks, and passed all seven implemented automated tests.

Remaining work includes verifying robots.txt compliance, reviewing potential duplicate requisitions, and finalizing the submission package.
