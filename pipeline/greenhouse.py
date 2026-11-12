import json
import logging
from .config import GREENHOUSE_BOARDS
from .scraper_utils import fetch_url
from .filters import is_relevant_title, is_us_or_us_remote

logger = logging.getLogger(__name__)

def scrape_greenhouse():
    records = []
    for board in GREENHOUSE_BOARDS:
        url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
        try:
            response = fetch_url(url, params={"content": "true"})
            if "json" not in (response["content_type"] or "").lower():
                logger.error("Greenhouse returned non-JSON for %s (%s)",
                             board, response["content_type"])
                continue
            payload = json.loads(response["body"])
            for job in payload.get("jobs", []):
                title = job.get("title", "")
                location = (job.get("location") or {}).get("name", "")
                content = job.get("content", "") or ""
                if not is_relevant_title(title):
                    continue
                if not is_us_or_us_remote(location, content):
                    continue
                records.append({
                    "source": "greenhouse",
                    "source_company": board,
                    "source_id": str(job.get("id", "")),
                    "title_raw": title,
                    "company_raw": board,
                    "location_raw": location,
                    "description_raw": content,
                    "source_url": job.get("absolute_url"),
                    "posted_at_raw": job.get("updated_at"),
                    "raw_payload": job,
                })
            logger.info("Greenhouse %s: retained %d matching jobs",
                        board, sum(r["source_company"] == board for r in records))
        except Exception:
            logger.exception("Greenhouse board failed: %s", board)
    return records
