
import html
import logging
import os
import random
import time

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from .schemas import ExtractionResult

# Load environment variables from the .env file
load_dotenv()

logger = logging.getLogger(__name__)

# Gemini model that worked with your API key
MODEL_NAME = "gemini-3.5-flash-lite"

# Retry configuration
MAX_RETRIES = 4
BASE_DELAY = 2
MAX_DELAY = 30


PROMPT = """
You are a precise job-posting information extractor.

Your task is to extract structured information from job postings
collected from Greenhouse, Lever, and Hacker News.

IMPORTANT INSTRUCTIONS:

1. Extract only information explicitly supported by the posting.

2. Never guess or hallucinate missing information.

3. Use null for missing scalar fields.

4. Use [] if no skills are explicitly mentioned.

5. A Hacker News comment may contain multiple job openings.
   Return one structured record for each relevant role.

6. Relevant roles include:
   - Data Engineer
   - Senior Data Engineer
   - Analytics Engineer
   - Machine Learning Engineer
   - ML Engineer
   - Data Platform Engineer
   - Platform Engineer

7. Seniority must be one of:
   junior, mid, senior, staff_plus, or null.

8. Remote policy must be one of:
   onsite, hybrid, remote, or null.

9. Employment type must be one of:
   full_time, contract, intern, or null.

10. Extract salary only when explicitly stated.
    Annualize only if the pay period is unambiguous.

11. Never infer visa sponsorship from silence.

12. For every populated field, provide an exact supporting
    snippet from the supplied source text in the evidence object.

13. Do not invent posting dates.

14. For Greenhouse and Lever, the job title and company are
    supplied as source metadata. Use those values when supported.

15. Do not reject a relevant engineering role simply because
    its description focuses on general software engineering.

16. Return an empty jobs list only if the posting contains
    no relevant engineering role.

17. Return valid JSON only, without markdown formatting.

EXPECTED JSON STRUCTURE:

{
  "jobs": [
    {
      "company": null,
      "title": null,
      "seniority": null,
      "city": null,
      "country": null,
      "remote_policy": null,
      "salary_min": null,
      "salary_max": null,
      "currency": null,
      "employment_type": null,
      "skills": [],
      "visa_sponsorship": null,
      "posted_date": null,
      "evidence": {}
    }
  ]
}
"""


def clean_description(text):
    """
    Convert HTML and HTML entities into readable text.

    Handles Greenhouse descriptions containing:
    - HTML tags
    - Encoded HTML entities
    - Double-encoded HTML
    """

    if not text:
        return ""

    cleaned = str(text)

    # Decode HTML entities up to three times
    for _ in range(3):
        decoded = html.unescape(cleaned)

        if decoded == cleaned:
            break

        cleaned = decoded

    # Parse the resulting HTML
    soup = BeautifulSoup(cleaned, "html.parser")

    # Remove non-content elements
    for tag in soup(["script", "style"]):
        tag.decompose()

    # Convert HTML into readable text
    cleaned_text = soup.get_text(
        separator=" ",
        strip=True
    )

    return cleaned_text


def get_client():
    """
    Initialize Gemini using the API key in .env.
    """

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not found. "
            "Please check your .env file."
        )

    return genai.Client(api_key=api_key)


def generate_with_retry(client, source_text):
    """
    Send the cleaned job description to Gemini.

    Retry temporary server failures using exponential
    backoff with random jitter.
    """

    for attempt in range(MAX_RETRIES):

        try:
            logger.info(
                "Gemini request attempt %d/%d",
                attempt + 1,
                MAX_RETRIES
            )

            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=source_text,
                config=types.GenerateContentConfig(
                    system_instruction=PROMPT,
                    response_mime_type="application/json",
                    temperature=0,
                ),
            )

            return response

        except errors.ServerError as exc:

            # Retry temporary server errors only
            if exc.code not in (500, 502, 503, 504):
                raise

            if attempt == MAX_RETRIES - 1:
                logger.error(
                    "Gemini failed after %d attempts: %s",
                    MAX_RETRIES,
                    exc
                )
                raise

            delay = min(
                BASE_DELAY * (2 ** attempt),
                MAX_DELAY
            )

            delay += random.uniform(0, 1)

            logger.warning(
                "Gemini server error %s. "
                "Retrying in %.1f seconds...",
                exc.code,
                delay
            )

            print(
                f"Gemini server busy (HTTP {exc.code}). "
                f"Retrying in {delay:.1f} seconds..."
            )

            time.sleep(delay)

    raise RuntimeError(
        "Gemini request failed after all retries."
    )


def extract_jobs(record, client=None):
    """
    Extract structured jobs from one raw posting.

    Args:
        record:
            Dictionary containing the raw posting.

        client:
            Optional Gemini client.

    Returns:
        Tuple containing:
        - Validated ExtractionResult
        - Token usage dictionary
    """

    if client is None:
        client = get_client()

    # Clean HTML from the original description
    description = clean_description(
        record.get("description_raw", "")
    )

    # Prepare the text sent to Gemini
    source_text = "\n".join([
        f"Company: {record.get('company_raw') or ''}",
        f"Title: {record.get('title_raw') or ''}",
        f"Location: {record.get('location_raw') or ''}",
        f"Description: {description}",
    ])

    # Limit input size to control token usage
    source_text = source_text[:20000]

    logger.info(
        "Extracting job information from source: %s",
        record.get("source")
    )

    # Call Gemini with automatic retries
    response = generate_with_retry(
        client,
        source_text
    )

    # Check for an empty response
    if not response.text:
        raise RuntimeError(
            "Gemini returned an empty response."
        )

    # Validate Gemini JSON using Pydantic
    try:
        result = ExtractionResult.model_validate_json(
            response.text
        )

    except ValidationError:
        logger.exception(
            "Gemini response failed Pydantic validation."
        )
        raise

    # Verify evidence snippets
    for job in result.jobs:

        for field, snippet in list(job.evidence.items()):

            if not snippet or snippet not in source_text:

                logger.warning(
                    "Invalid evidence snippet for field: %s",
                    field
                )

                del job.evidence[field]

    # Extract token usage
    usage = response.usage_metadata

    usage_data = {
        "model": MODEL_NAME,

        "input_tokens": (
            usage.prompt_token_count if usage else 0
        ) or 0,

        "output_tokens": (
            usage.candidates_token_count if usage else 0
        ) or 0,

        "total_tokens": (
            usage.total_token_count if usage else 0
        ) or 0,
    }

    logger.info(
        "Extraction completed. Jobs found: %d",
        len(result.jobs)
    )

    logger.info(
        "Token usage: input=%d, output=%d, total=%d",
        usage_data["input_tokens"],
        usage_data["output_tokens"],
        usage_data["total_tokens"]
    )

    return result, usage_data
