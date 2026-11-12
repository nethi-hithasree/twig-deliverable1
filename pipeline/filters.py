
import re


# --------------------------------------------------
# Relevant engineering job titles
# --------------------------------------------------

ROLE_PATTERNS = [
    r"\bdata\s+(?:platform\s+)?engineer(?:ing)?\b",
    r"\bmachine\s+learning\s+engineer(?:ing)?\b",
    r"\bml\s+engineer(?:ing)?\b",
    r"\banalytics\s+engineer(?:ing)?\b",
    r"\bplatform\s+engineer(?:ing)?\b",
    r"\bengineer(?:ing)?\s*[,/-]\s*(?:data|ml|platform|analytics)\b",
    r"\bdata\s+scientist\b",
    r"\bdata\s+analyst\b",
    r"\banalytics\s+analyst\b",
    r"\bbusiness\s+intelligence\s+(?:engineer|analyst)\b",
    r"\bmlops\s+engineer\b",
    r"\bai\s+engineer\b",
    r"\b(?:data|ml|analytics)\s+infrastructure\s+engineer\b",
    r"\bsoftware\s+engineer\s*[-/,]\s*(?:data|ml|platform|infrastructure)\b",
]

ROLE_REGEX = re.compile(
    "|".join(ROLE_PATTERNS),
    re.IGNORECASE,
)


# --------------------------------------------------
# US location detection
# --------------------------------------------------

US_LOCATION_NAMES = [
    "United States",
    "USA",
    "U.S.",
    "San Francisco",
    "New York",
    "New York City",
    "NYC",
    "Seattle",
    "Austin",
    "Boston",
    "Chicago",
    "Los Angeles",
    "Denver",
    "Atlanta",
    "Washington DC",
    "Washington, DC",
    "Washington, D.C.",
    "Portland",
    "Miami",
    "Dallas",
    "Houston",
    "San Diego",
    "San Jose",
    "Palo Alto",
    "Mountain View",
    "Menlo Park",
    "Sunnyvale",
    "Redwood City",
    "Berkeley",
    "Oakland",
    "Philadelphia",
    "Pittsburgh",
    "Raleigh",
    "Durham",
    "Charlotte",
    "Salt Lake City",
    "Phoenix",
    "Minneapolis",
    "Detroit",
    "Nashville",
    "Madison",
    "Boulder",
    "Cambridge",
    "California",
    "Texas",
    "Massachusetts",
    "Colorado",
    "Florida",
    "Virginia",
    "Oregon",
    "Arizona",
    "Utah",
    "Ohio",
    "Michigan",
    "North Carolina",
    "New Jersey",
    "Pennsylvania",
    "Washington State",
]

US_LOCATIONS = re.compile(
    r"(?<!\w)(?:"
    + "|".join(
        re.escape(name)
        for name in US_LOCATION_NAMES
    )
    + r")(?!\w)",
    re.IGNORECASE,
)


US_REMOTE = re.compile(
    r"\b(?:US|USA|U\.S\.|United States)"
    r"\s*[-/(),: ]*\s*remote\b"
    r"|\bremote\s*[-/(),: ]*\s*"
    r"(?:US|USA|U\.S\.|United States)\b"
    r"|\bremote\s*\(\s*(?:US|USA|U\.S\.)\s*\)",
    re.IGNORECASE,
)


# --------------------------------------------------
# Broader Hacker News candidate detection
# --------------------------------------------------

HN_ROLE_PATTERNS = [
    r"\bdata\b",
    r"\banalytics?\b",
    r"\bmachine\s+learning\b",
    r"\bML\b",
    r"\bAI\b",
    r"\bMLOps\b",
    r"\bplatform\b",
    r"\binfrastructure\b",
    r"\bbackend\b",
    r"\bdata\s+science\b",
    r"\bscientist\b",
    r"\bengineer(?:ing)?\b",
    r"\bPython\b",
    r"\bSQL\b",
    r"\bSpark\b",
    r"\bPyTorch\b",
    r"\bTensorFlow\b",
]

HN_ROLE_REGEX = re.compile(
    "|".join(HN_ROLE_PATTERNS),
    re.IGNORECASE,
)


HN_HIRING_REGEX = re.compile(
    r"\b(?:hiring|we're hiring|we are hiring|"
    r"open roles?|open positions?|"
    r"join our team|apply here|careers?|"
    r"job openings?|full[- ]time|"
    r"looking for)\b",
    re.IGNORECASE,
)


HN_REMOTE_REGEX = re.compile(
    r"\bremote\b"
    r"|\bhybrid\b"
    r"|\bonsite\b"
    r"|\bon[- ]site\b",
    re.IGNORECASE,
)


# --------------------------------------------------
# Public filtering functions
# --------------------------------------------------

def is_relevant_title(title):
    """
    Return True for relevant data, ML,
    analytics and platform engineering titles.
    """
    if not title:
        return False

    return bool(ROLE_REGEX.search(str(title)))


def is_us_or_us_remote(location_text, description=""):
    """
    Preliminary US location check.

    Use the posting's location field rather than
    incidental locations mentioned in descriptions.
    """
    location = str(location_text or "")

    if US_REMOTE.search(location):
        return True

    if US_LOCATIONS.search(location):
        return True

    return False


def is_hn_candidate(text):
    """
    Broadly identify Hacker News hiring candidates.

    This is a recall-oriented first-pass filter.
    Final extraction and validation must establish
    actual job titles and US eligibility.
    """
    if not text:
        return False

    text = str(text).strip()

    if len(text) < 40:
        return False

    has_relevant_title = bool(
        ROLE_REGEX.search(text)
    )

    has_role_signal = bool(
        HN_ROLE_REGEX.search(text)
    )

    has_hiring_signal = bool(
        HN_HIRING_REGEX.search(text)
    )

    has_us_location = bool(
        US_LOCATIONS.search(text)
        or US_REMOTE.search(text)
    )

    has_remote_signal = bool(
        HN_REMOTE_REGEX.search(text)
    )

    # Strongest case: relevant title and US location.
    if has_relevant_title and has_us_location:
        return True

    # Relevant title with remote/hiring indication.
    if has_relevant_title and (
        has_remote_signal or has_hiring_signal
    ):
        return True

    # Broader candidate: role-related language,
    # hiring signal, and geographic/remote signal.
    if (
        has_role_signal
        and has_hiring_signal
        and (has_us_location or has_remote_signal)
    ):
        return True

    return False
