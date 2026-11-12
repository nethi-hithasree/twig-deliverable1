import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
LOG_DIR = ROOT / "logs"
OUTPUT_FILE = ROOT / "data" / "scraped_jobs.jsonl"
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
CACHE_TTL_HOURS = float(os.getenv("CACHE_TTL_HOURS", "24"))
RATE_LIMIT_SECONDS = float(os.getenv("RATE_LIMIT_SECONDS", "1.0"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "4"))

GREENHOUSE_BOARDS = ["stripe", "airbnb", "databricks", "figma"]
LEVER_SITES = ["palantir", "plaid"]
