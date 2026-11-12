
import re
from typing import Optional

from .schemas import JobExtraction
from .filters import is_relevant_title


# --------------------------------------------------
# US COUNTRY NAMES
# --------------------------------------------------

US_COUNTRIES = {
    "us",
    "usa",
    "u.s.",
    "u.s.a.",
    "united states",
    "united states of america",
}


# --------------------------------------------------
# RECOGNIZED US CITIES
# --------------------------------------------------

# Conservative mapping for US job locations.
# Add more cities only after geographic verification.

US_CITY_NAMES = {
    "seattle",
    "south san francisco",
    "san francisco",
    "new york city",
    "new york",
    "austin",
    "boston",
    "chicago",
    "denver",
    "atlanta",
    "los angeles",
    "washington dc",
    "miami",
    "dallas",
    "houston",
    "phoenix",
    "san jose",
    "san diego",
    "mountain view",
    "palo alto",
    "menlo park",
    "sunnyvale",
    "redwood city",
    "philadelphia",
    "raleigh",
    "durham",
    "portland",
}


# --------------------------------------------------
# US STATE ABBREVIATIONS
# --------------------------------------------------

US_STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE",
    "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS",
    "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY",
    "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "DC",
}


# --------------------------------------------------
# COUNTRY NORMALIZATION
# --------------------------------------------------

def normalize_country(country: Optional[str]):
    """
    Normalize explicitly stated country values.

    Examples:
        USA -> US
        United States -> US
        Canada -> Canada
    """

    if not country:
        return None

    value = country.strip()

    if value.lower() in US_COUNTRIES:
        return "US"

    return value


# --------------------------------------------------
# LOCATION PARSING
# --------------------------------------------------

def parse_us_locations(location_text):
    """
    Parse recognized US cities from a location string.

    Returns:
        (cities, unknown_locations)

    Examples:
        Seattle
            -> (["Seattle"], [])

        Seattle, South San Francisco
            -> (["Seattle", "South San Francisco"], [])

        San Francisco, New York City, Seattle
            -> (["San Francisco", "New York City", "Seattle"], [])
    """

    if not location_text:
        return [], []

    parts = re.split(
        r"\s*[,;|/]\s*",
        location_text
    )

    cities = []
    unknown = []

    for part in parts:

        part = part.strip()

        if not part:
            continue

        normalized = part.lower()

        if normalized in US_CITY_NAMES:
            cities.append(part)

        elif normalized.upper() in US_STATE_CODES:
            # State abbreviation associated with a city.
            continue

        else:
            unknown.append(part)

    return list(dict.fromkeys(cities)), unknown


# --------------------------------------------------
# EVIDENCE VALIDATION
# --------------------------------------------------

def validate_evidence(
    job: JobExtraction,
    source_text: str
):
    """
    Remove extracted scalar values that lack
    supporting evidence in the source text.

    This is a textual evidence check, not a
    complete semantic verification.
    """

    fields = [
        "company",
        "title",
        "seniority",
        "city",
        "country",
        "remote_policy",
        "salary_min",
        "salary_max",
        "currency",
        "employment_type",
        "visa_sponsorship",
        "posted_date",
    ]

    for field in fields:

        value = getattr(job, field)

        if value is None:
            continue

        snippet = job.evidence.get(field)

        if (
            not isinstance(snippet, str)
            or not snippet.strip()
            or snippet not in source_text
        ):
            setattr(job, field, None)

    # Verify extracted skills against source text.
    valid_skills = []

    for skill in job.skills:

        if re.search(
            re.escape(skill),
            source_text,
            re.IGNORECASE
        ):
            valid_skills.append(skill)

    job.skills = valid_skills

    return job


# --------------------------------------------------
# MAIN JOB VALIDATION
# --------------------------------------------------

def validate_job(
    job: JobExtraction,
    source_text: str
):
    """
    Validate an extracted job.

    Checks:
        1. Evidence
        2. Relevant engineering title
        3. US location normalization
        4. Multiple-city handling
        5. Country inference evidence
        6. Salary consistency

    Returns:
        (validated_job, warnings)
    """

    warnings = []

    # ----------------------------------------------
    # STEP 1: VALIDATE EVIDENCE
    # ----------------------------------------------

    job = validate_evidence(
        job,
        source_text
    )

    # ----------------------------------------------
    # STEP 2: VALIDATE JOB TITLE
    # ----------------------------------------------

    if not job.title:

        warnings.append(
            "Missing supported job title"
        )

        return None, warnings

    if not is_relevant_title(job.title):

        warnings.append(
            "Irrelevant job title"
        )

        return None, warnings

    # ----------------------------------------------
    # STEP 3: NORMALIZE COUNTRY
    # ----------------------------------------------

    job.country = normalize_country(
        job.country
    )

    # ----------------------------------------------
    # STEP 4: PARSE US LOCATIONS
    # ----------------------------------------------

    original_city = job.city

    cities, unknown = parse_us_locations(
        original_city
    )

    if unknown:

        warnings.append(
            "Unrecognized locations: "
            + ", ".join(unknown)
        )

    # ----------------------------------------------
    # STEP 5: HANDLE RECOGNIZED US CITIES
    # ----------------------------------------------

    if cities and not unknown:

        # Preserve all recognized cities.
        job.city = ", ".join(cities)

        if job.country is None:

            # Infer US from recognized US cities.
            job.country = "US"

            # Preserve source evidence for the inference.
            # This is NOT an explicit country statement.
            if original_city:

                snippet = original_city

                if snippet in source_text:
                    job.evidence["country"] = snippet

                else:
                    # Find the actual location phrase
                    # from the source text.
                    for line in source_text.splitlines():

                        if line.startswith("Location:"):

                            location_value = line.split(
                                "Location:", 1
                            )[1].strip()

                            if location_value:
                                job.evidence["country"] = (
                                    location_value
                                )

                            break

            warnings.append(
                "US country inferred from recognized US "
                "cities; country not explicitly stated"
            )

        elif job.country != "US":

            warnings.append(
                "Country conflicts with US city mapping; "
                "manual review required"
            )

            return None, warnings

    # ----------------------------------------------
    # STEP 6: HANDLE MIXED LOCATIONS
    # ----------------------------------------------

    elif cities and unknown:

        job.city = original_city

        warnings.append(
            "Mixed or ambiguous locations; "
            "manual review required"
        )

        return None, warnings

    # ----------------------------------------------
    # STEP 7: HANDLE UNCONFIRMED LOCATIONS
    # ----------------------------------------------

    else:

        warnings.append(
            "US location not confirmed; "
            "manual review required"
        )

        return None, warnings

    # ----------------------------------------------
    # STEP 8: VALIDATE SALARY
    # ----------------------------------------------

    if (
        job.salary_min is not None
        and job.salary_max is not None
        and job.salary_min > job.salary_max
    ):

        warnings.append(
            "Salary minimum exceeds maximum"
        )

        job.salary_min = None
        job.salary_max = None
        job.currency = None

    # ----------------------------------------------
    # STEP 9: RETURN VALIDATED JOB
    # ----------------------------------------------

    return job, warnings
