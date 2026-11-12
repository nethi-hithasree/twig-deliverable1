
import json
import logging

from bs4 import BeautifulSoup
from requests.exceptions import HTTPError

from .config import LEVER_SITES
from .scraper_utils import fetch_url, is_html
from .filters import is_relevant_title, is_us_or_us_remote

logger = logging.getLogger(__name__)


def _plain_text(value):
    """Convert HTML or Lever rich-text content into plain text."""
    if not value:
        return ""

    if isinstance(value, dict):
        value = value.get("content", "")

    return BeautifulSoup(
        str(value), "html.parser"
    ).get_text(" ", strip=True)


def _description(job):
    """Combine available job-description fields."""
    parts = [
        job.get("description"),
        job.get("descriptionBody"),
        job.get("additional"),
    ]

    return " ".join(
        text
        for part in parts
        if (text := _plain_text(part))
    )


def scrape_lever():
    """
    Collect relevant US and US-remote jobs from Lever.

    An unavailable company board is skipped without
    stopping collection from other companies.
    """
    records = []

    for site in LEVER_SITES:
        site = str(site).strip()

        if not site:
            continue

        url = f"https://api.lever.co/v0/postings/{site}"

        logger.info("Checking Lever board: %s", site)

        try:
            response = fetch_url(
                url,
                params={"mode": "json"},
            )

        except Exception as exc:
            # An unavailable board must not stop other sources.
            logger.warning(
                "Skipping Lever board %s: %s",
                site,
                exc,
            )
            continue

        if is_html(
            response.get("content_type", ""),
            response.get("body", ""),
        ):
            logger.warning(
                "Skipping Lever %s: HTML returned instead of JSON",
                site,
            )
            continue

        try:
            payload = json.loads(response["body"])

        except (json.JSONDecodeError, KeyError, TypeError):
            logger.warning(
                "Skipping Lever %s: invalid JSON response",
                site,
            )
            continue

        if not isinstance(payload, list):
            logger.warning(
                "Skipping Lever %s: unexpected response type %s",
                site,
                type(payload).__name__,
            )
            continue

        retained = 0

        for job in payload:
            if not isinstance(job, dict):
                continue

            title = job.get("text") or ""
            categories = job.get("categories") or {}

            if not isinstance(categories, dict):
                categories = {}

            location = categories.get("location") or ""
            description = _description(job)

            if not is_relevant_title(title):
                continue

            if not is_us_or_us_remote(
                location, description
            ):
                continue

            records.append({
                "source": "lever",
                "source_company": site,
                "source_id": str(job.get("id") or ""),
                "title_raw": title,
                "company_raw": site,
                "location_raw": location,
                "description_raw": description,
                "source_url": (
                    job.get("hostedUrl")
                    or job.get("applyUrl")
                ),
                "posted_at_raw": job.get("createdAt"),
                "raw_payload": job,
            })

            retained += 1

        logger.info(
            "Lever %s: retained %d matching jobs",
            site,
            retained,
        )

    logger.info(
        "Lever collection complete: %d records",
        len(records),
    )

    return records
