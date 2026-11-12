
"""
Twig Deliverable 1 - Job Extraction Schemas

Pydantic models for structured Gemini extraction.

Features:
- Optional job fields
- Normalized evidence dictionaries
- Boolean visa sponsorship normalization
- Flexible skills parsing
- Compatibility with the existing validator
"""

from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class JobExtraction(BaseModel):
    """
    Represents one job extracted from a source posting.

    Missing optional information is represented as None.

    Evidence remains a dictionary because validator.py
    accesses evidence using job.evidence.get(field).
    """

    model_config = ConfigDict(extra="ignore")

    # Company information
    company: Optional[str] = None
    title: Optional[str] = None
    seniority: Optional[str] = None

    # Location
    city: Optional[str] = None
    country: Optional[str] = None
    remote_policy: Optional[str] = None

    # Compensation
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    currency: Optional[str] = None

    # Employment details
    employment_type: Optional[str] = None

    # Technical skills
    skills: list[str] = Field(default_factory=list)

    # Additional fields
    visa_sponsorship: Optional[str] = None
    posted_date: Optional[str] = None

    # Source evidence
    evidence: dict[str, str] = Field(
        default_factory=dict
    )

    @field_validator(
        "company",
        "title",
        "seniority",
        "city",
        "country",
        "remote_policy",
        "currency",
        "employment_type",
        "posted_date",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value):
        """
        Convert empty strings into None.
        """
        if value is None:
            return None

        if isinstance(value, str):
            value = value.strip()
            return value if value else None

        return value

    @field_validator("visa_sponsorship", mode="before")
    @classmethod
    def normalize_visa_sponsorship(cls, value):
        """
        Normalize Gemini sponsorship responses.

        true  -> "yes"
        false -> "no"
        null  -> None

        Unknown values remain unknown rather than
        being converted into unsupported claims.
        """
        if value is None:
            return None

        if isinstance(value, bool):
            return "yes" if value else "no"

        if isinstance(value, str):
            normalized = value.strip().lower()

            if normalized in ("yes", "true"):
                return "yes"

            if normalized in ("no", "false"):
                return "no"

            if normalized in (
                "",
                "unknown",
                "not specified",
                "not mentioned",
                "n/a",
                "null",
            ):
                return None

            return normalized

        raise ValueError(
            "Invalid visa sponsorship value"
        )

    @field_validator("skills", mode="before")
    @classmethod
    def normalize_skills(cls, value):
        """
        Normalize skills from Gemini.

        Accepts:
        - None
        - comma-separated string
        - list of strings
        """
        if value is None:
            return []

        if isinstance(value, str):
            return [
                skill.strip()
                for skill in value.split(",")
                if skill.strip()
            ]

        if isinstance(value, list):
            return [
                skill.strip()
                for skill in value
                if isinstance(skill, str)
                and skill.strip()
            ]

        return value

    @field_validator("evidence", mode="before")
    @classmethod
    def normalize_evidence(cls, value):
        """
        Normalize Gemini evidence while preserving
        dictionary compatibility.

        Examples:

        None -> {}

        {"skills": None}
            -> {"skills": ""}

        {"skills": ["Python", "SQL"]}
            -> {"skills": "Python | SQL"}

        Empty evidence remains empty and must not
        be treated as verified source evidence.
        """
        if value is None:
            return {}

        if isinstance(value, BaseModel):
            value = value.model_dump()

        if not isinstance(value, dict):
            raise ValueError(
                "Evidence must be a dictionary"
            )

        normalized = {}

        for field, snippet in value.items():

            if snippet is None:
                normalized[field] = ""

            elif isinstance(snippet, str):
                normalized[field] = snippet.strip()

            elif isinstance(snippet, list):
                normalized[field] = " | ".join(
                    item.strip()
                    for item in snippet
                    if isinstance(item, str)
                    and item.strip()
                )

            else:
                normalized[field] = ""

        return normalized


class ExtractionResult(BaseModel):
    """
    Top-level response returned by Gemini.

    Example:

    {
        "jobs": [
            {
                "company": "Stripe",
                "title": "Machine Learning Engineer",
                "visa_sponsorship": false,
                "skills": ["Python", "SQL"],
                "evidence": {
                    "title": "Machine Learning Engineer",
                    "skills": ["Python", "SQL"]
                }
            }
        ]
    }
    """

    model_config = ConfigDict(extra="ignore")

    jobs: list[JobExtraction] = Field(
        default_factory=list
    )
