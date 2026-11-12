
import logging
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse, parse_qs

from bs4 import BeautifulSoup

from .scraper_utils import fetch_url
from .filters import is_hn_candidate

logger = logging.getLogger(__name__)

HN_BASE = "https://news.ycombinator.com"
SUBMITTED_URL = f"{HN_BASE}/submitted?id=whoishiring"


def _current_month_thread():
    """
    Find the current month's Who is hiring thread.
    Follow pagination on the submitted page.
    """
    month = datetime.now().strftime("%B")
    year = datetime.now().year

    expected_title = f"Who is hiring? ({month} {year})"

    page_url = SUBMITTED_URL
    visited = set()

    while page_url and page_url not in visited:
        visited.add(page_url)

        response = fetch_url(page_url)
        soup = BeautifulSoup(
            response["body"], "html.parser"
        )

        for link in soup.select("span.titleline > a"):
            title = link.get_text(" ", strip=True)

            if expected_title.lower() in title.lower():
                thread_url = urljoin(
                    HN_BASE,
                    link.get("href", "")
                )

                logger.info(
                    "Found hiring thread: %s",
                    thread_url,
                )

                return thread_url, title

        more = soup.select_one("a.morelink")

        page_url = (
            urljoin(HN_BASE, more["href"])
            if more and more.get("href")
            else None
        )

    raise RuntimeError(
        f"Could not locate {expected_title}"
    )


def _comment_depth(row):
    """
    Return HN comment indentation depth.
    Top-level comments normally have width 0.
    """
    indent = row.select_one("td.ind img")

    if indent is None:
        return 0

    try:
        return int(indent.get("width", "0"))
    except (ValueError, TypeError):
        return 0


def _parse_comments(html, thread_url, thread_title):
    """
    Extract candidate hiring comments and
    return the next pagination URL.
    """
    soup = BeautifulSoup(
        html, "html.parser"
    )

    records = []

    all_comments = soup.select("tr.athing.comtr")

    logger.info(
        "HN HTML contains %d comment rows",
        len(all_comments),
    )

    top_level_count = 0
    filtered_count = 0

    for row in all_comments:
        comment_id = row.get("id")

        comment_cell = row.select_one(".commtext")

        if not comment_id or not comment_cell:
            continue

        depth = _comment_depth(row)

        # Only process top-level hiring comments.
        if depth > 0:
            continue

        top_level_count += 1

        text = comment_cell.get_text(
            " ", strip=True
        )

        if not text:
            continue

        if not is_hn_candidate(text):
            filtered_count += 1
            continue

        author = row.select_one(".hnuser")

        records.append({
            "source": "hackernews",
            "source_company": None,
            "source_id": comment_id,
            "title_raw": None,
            "company_raw": None,
            "location_raw": None,
            "description_raw": text,
            "source_url": (
                f"{HN_BASE}/item?id={comment_id}"
            ),
            "posted_at_raw": None,
            "hn_author": (
                author.get_text(strip=True)
                if author else None
            ),
            "hn_thread_title": thread_title,
            "raw_payload": {
                "comment_id": comment_id,
                "comment_text_html": str(comment_cell),
            },
        })

    more = soup.select_one("a.morelink")

    next_url = (
        urljoin(HN_BASE, more["href"])
        if more and more.get("href")
        else None
    )

    logger.info(
        "HN diagnostics: total=%d, top_level=%d, "
        "filtered=%d, retained=%d, has_more=%s",
        len(all_comments),
        top_level_count,
        filtered_count,
        len(records),
        bool(next_url),
    )

    return records, next_url


def scrape_hackernews():
    """
    Scrape the monthly Hacker News hiring thread,
    following available pagination links.
    """
    records = []

    try:
        thread_url, thread_title = (
            _current_month_thread()
        )

        logger.info(
            "Hacker News thread: %s",
            thread_title,
        )

        page_url = thread_url
        visited = set()
        seen_comments = set()

        page_number = 0

        while page_url and page_url not in visited:
            visited.add(page_url)
            page_number += 1

            logger.info(
                "Fetching HN page %d: %s",
                page_number,
                page_url,
            )

            response = fetch_url(page_url)

            page_records, next_url = (
                _parse_comments(
                    response["body"],
                    thread_url,
                    thread_title,
                )
            )

            for record in page_records:
                source_id = record["source_id"]

                if source_id in seen_comments:
                    continue

                seen_comments.add(source_id)
                records.append(record)

            logger.info(
                "HN page %d: %d candidate comments",
                page_number,
                len(page_records),
            )

            if not next_url:
                logger.info(
                    "HN pagination finished: no More link"
                )
                break

            if next_url in visited:
                logger.warning(
                    "HN pagination loop detected: %s",
                    next_url,
                )
                break

            page_url = next_url

        logger.info(
            "Hacker News complete: %d unique "
            "candidate comments across %d pages",
            len(records),
            page_number,
        )

    except Exception:
        logger.exception(
            "Hacker News scraping failed"
        )

    return records
