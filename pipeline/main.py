import json
import logging
from datetime import datetime, timezone

from .config import OUTPUT_FILE
from .logging_config import configure_logging
from .greenhouse import scrape_greenhouse
from .lever import scrape_lever
from .hackernews import scrape_hackernews
from .scraper_utils import append_jsonl

logger = logging.getLogger(__name__)

def run():
    configure_logging()
    logger.info("Starting Twig job-posting collection")
    all_records = []
    # Each source function catches its own failures, so one source cannot
    # prevent the other sources from being collected.
    for source_name, scraper in [
        ("greenhouse", scrape_greenhouse),
        ("lever", scrape_lever),
        ("hackernews", scrape_hackernews),
    ]:
        try:
            records = scraper()
            all_records.extend(records)
            logger.info("%s completed: %d records", source_name, len(records))
        except Exception:
            logger.exception("Unexpected failure in %s", source_name)

    run_time = datetime.now(timezone.utc).isoformat()
    for record in all_records:
        record["collected_at"] = run_time

    # JSONL is an append-only raw collection log for this first deliverable.
    append_jsonl(all_records, OUTPUT_FILE)
    logger.info("Collection complete. Total candidate records: %d", len(all_records))
    logger.info("Output: %s", OUTPUT_FILE)
    return all_records

if __name__ == "__main__":
    run()
