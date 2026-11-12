
from unittest.mock import Mock, patch

import pytest

from pipeline import scraper_utils


@pytest.fixture(autouse=True)
def clear_robots_cache():
    scraper_utils._robots_cache.clear()
    yield
    scraper_utils._robots_cache.clear()


def mock_response(status_code, body=""):
    response = Mock()
    response.status_code = status_code
    response.text = body
    return response


def test_robots_allows_public_path():
    robots = """
User-agent: *
Disallow: /private/
Allow: /
"""
    with patch(
        "pipeline.scraper_utils.requests.get",
        return_value=mock_response(200, robots),
    ):
        assert scraper_utils.check_robots_permission(
            "https://example.com/jobs"
        ) is True


def test_robots_blocks_private_path():
    robots = """
User-agent: *
Disallow: /private/
"""
    with patch(
        "pipeline.scraper_utils.requests.get",
        return_value=mock_response(200, robots),
    ):
        assert scraper_utils.check_robots_permission(
            "https://example.com/private/jobs"
        ) is False


def test_robots_missing_file():
    with patch(
        "pipeline.scraper_utils.requests.get",
        return_value=mock_response(404),
    ):
        assert scraper_utils.check_robots_permission(
            "https://example.com/jobs"
        ) is True


def test_robots_server_error():
    with patch(
        "pipeline.scraper_utils.requests.get",
        return_value=mock_response(503),
    ):
        with pytest.raises(RuntimeError):
            scraper_utils.check_robots_permission(
                "https://example.com/jobs"
            )


def test_fetch_blocks_disallowed_path():
    robots = """
User-agent: *
Disallow: /private/
"""
    with patch(
        "pipeline.scraper_utils.requests.get",
        return_value=mock_response(200, robots),
    ) as mocked_get:
        with pytest.raises(PermissionError):
            scraper_utils.fetch_url(
                "https://example.com/private/jobs",
                use_cache=False,
            )

        # Only robots.txt should be requested.
        assert mocked_get.call_count == 1
