
import hashlib
import json
import logging
import time

from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse, urlencode
from urllib.robotparser import RobotFileParser

import requests

from .config import (
    RAW_DIR,
    REQUEST_TIMEOUT,
    CACHE_TTL_HOURS,
    RATE_LIMIT_SECONDS,
    MAX_RETRIES,
)

logger = logging.getLogger(__name__)

USER_AGENT = (
    "TwigTakeHomeJobResearch/1.0 "
    "(polite public job-board collector)"
)

_last_request_by_domain = {}
_robots_cache = {}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def stable_hash(value):
    return hashlib.sha256(
        str(value).encode("utf-8")
    ).hexdigest()


def cache_path(url):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    return RAW_DIR / f"{stable_hash(url)}.json"


def read_cache(url):
    path = cache_path(url)

    if not path.exists():
        return None

    try:
        cached = json.loads(
            path.read_text(encoding="utf-8")
        )

        fetched_at = datetime.fromisoformat(
            cached["fetched_at"]
        )

        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(
                tzinfo=timezone.utc
            )

        age = datetime.now(timezone.utc) - fetched_at

        if age <= timedelta(hours=CACHE_TTL_HOURS):
            logger.info("Cache hit: %s", url)
            return cached

    except (
        ValueError,
        KeyError,
        TypeError,
        OSError,
    ) as exc:
        logger.warning(
            "Ignoring invalid cache %s: %s",
            path,
            exc,
        )

    return None


def write_cache(url, status_code, content_type, body_text):
    payload = {
        "url": url,
        "fetched_at": utc_now(),
        "status_code": status_code,
        "content_type": content_type,
        "body": body_text,
    }

    path = cache_path(url)

    temporary = path.with_suffix(".tmp")

    temporary.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    temporary.replace(path)

    return path


def _respect_rate_limit(url, minimum_delay=None):
    domain = urlparse(url).netloc.lower()

    delay = float(RATE_LIMIT_SECONDS)

    if minimum_delay is not None:
        delay = max(delay, float(minimum_delay))

    previous = _last_request_by_domain.get(domain)

    if previous is not None:
        elapsed = time.monotonic() - previous
        wait = delay - elapsed

        if wait > 0:
            time.sleep(wait)

    _last_request_by_domain[domain] = time.monotonic()


def _robots_url(url):
    parsed = urlparse(url)

    return (
        f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    )


def _get_robots_parser(url):
    parsed_url = urlparse(url)

    if parsed_url.scheme not in ("http", "https"):
        raise ValueError("Only HTTP(S) URLs are supported")

    origin = (
        f"{parsed_url.scheme}://{parsed_url.netloc}"
    )

    if origin in _robots_cache:
        return _robots_cache[origin]

    robots_url = _robots_url(url)

    logger.info(
        "Checking robots.txt: %s",
        robots_url,
    )

    _respect_rate_limit(robots_url)

    try:
        response = requests.get(
            robots_url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/plain,*/*;q=0.8",
            },
            timeout=REQUEST_TIMEOUT,
        )

    except requests.RequestException as exc:
        raise RuntimeError(
            f"Unable to check robots.txt for {origin}: {exc}"
        ) from exc

    # Missing robots.txt normally means no explicit
    # robots restrictions are published.
    if response.status_code in (404, 410):
        parser = RobotFileParser()
        parser.parse([])
        _robots_cache[origin] = parser
        return parser

    if response.status_code in (401, 403):
        raise PermissionError(
            f"robots.txt access denied for {origin}"
        )

    if response.status_code >= 400:
        raise RuntimeError(
            f"robots.txt returned HTTP "
            f"{response.status_code} for {origin}"
        )

    parser = RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(response.text.splitlines())

    _robots_cache[origin] = parser

    return parser


def check_robots_permission(url):
    """
    Return True if robots.txt allows the URL.

    Raise an exception if robots.txt cannot be
    checked reliably.
    """
    parser = _get_robots_parser(url)

    allowed = parser.can_fetch(
        USER_AGENT,
        url,
    )

    if not allowed:
        logger.warning(
            "Blocked by robots.txt: %s",
            url,
        )

    return allowed


def fetch_url(
    url,
    *,
    headers=None,
    params=None,
    use_cache=True,
):
    """
    Fetch a URL with:
    - robots.txt permission checks
    - per-domain rate limiting
    - HTTP caching
    - retry handling
    """

    if not url.startswith(("http://", "https://")):
        raise ValueError(
            f"Unsupported URL: {url}"
        )

    request_url = url

    if params:
        query = urlencode(
            sorted(params.items()),
            doseq=True,
        )

        separator = (
            "&" if "?" in url else "?"
        )

        request_url = f"{url}{separator}{query}"

    # Check robots permission even for cached content.
    if not check_robots_permission(request_url):
        raise PermissionError(
            f"Robots.txt disallows: {request_url}"
        )

    parser = _get_robots_parser(request_url)

    crawl_delay = parser.crawl_delay(USER_AGENT)

    effective_delay = max(
        float(RATE_LIMIT_SECONDS),
        float(crawl_delay or 0),
    )

    if use_cache:
        cached = read_cache(request_url)

        if cached is not None:
            return cached

    request_headers = {
        "User-Agent": USER_AGENT,
        "Accept": (
            "application/json,"
            "text/html;q=0.9,"
            "*/*;q=0.8"
        ),
    }

    if headers:
        request_headers.update(headers)

    last_error = None

    for attempt in range(MAX_RETRIES):

        try:
            _respect_rate_limit(
                request_url,
                minimum_delay=effective_delay,
            )

            response = requests.get(
                url,
                headers=request_headers,
                params=params,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=False,
            )

            # Redirects require a separate robots.txt
            # check at the destination.
            if 300 <= response.status_code < 400:
                raise RuntimeError(
                    "HTTP redirect requires a separately "
                    f"authorized request: {response.headers.get('Location')}"
                )

            status = response.status_code

            # Permanent client errors should not retry.
            if 400 <= status < 500 and status != 429:
                response.raise_for_status()

            # Retry 429 and transient server errors.
            if status == 429 or status >= 500:
                raise requests.HTTPError(
                    f"Transient HTTP status {status}",
                    response=response,
                )

            response.raise_for_status()

            content_type = response.headers.get(
                "Content-Type",
                "",
            )

            body = response.text

            write_cache(
                request_url,
                response.status_code,
                content_type,
                body,
            )

            return {
                "url": response.url,
                "fetched_at": utc_now(),
                "status_code": response.status_code,
                "content_type": content_type,
                "body": body,
            }

        except requests.HTTPError as exc:
            status = (
                exc.response.status_code
                if exc.response is not None
                else None
            )

            # Do not retry permanent HTTP errors.
            if (
                status is not None
                and 400 <= status < 500
                and status != 429
            ):
                raise

            last_error = exc

        except requests.RequestException as exc:
            last_error = exc

        if attempt < MAX_RETRIES - 1:
            wait = min(2 ** attempt, 16)

            if (
                isinstance(last_error, requests.HTTPError)
                and last_error.response is not None
                and last_error.response.status_code == 429
            ):
                retry_after = last_error.response.headers.get(
                    "Retry-After"
                )

                if retry_after:
                    try:
                        wait = max(
                            wait,
                            float(retry_after),
                        )
                    except ValueError:
                        pass

            logger.warning(
                "Fetch attempt %d/%d failed for %s: %s",
                attempt + 1,
                MAX_RETRIES,
                request_url,
                last_error,
            )

            time.sleep(wait)

    raise RuntimeError(
        f"Could not fetch {request_url}: {last_error}"
    )


def is_html(content_type, body=""):
    return (
        "text/html" in (content_type or "").lower()
        or body.lstrip().lower().startswith(
            ("<!doctype html", "<html")
        )
    )


def append_jsonl(records, output_path):
    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "a",
        encoding="utf-8",
    ) as file:
        for record in records:
            file.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                    default=str,
                ) + "\n"
            )
