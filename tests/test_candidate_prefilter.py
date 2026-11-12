
import pytest

from pipeline.candidate_prefilter import classify_candidate


@pytest.mark.parametrize(
    "title",
    [
        "Senior Data Engineer",
        "Machine Learning Engineer",
        "Analytics Engineer",
        "Platform Engineer",
    ],
)
def test_structured_source_candidates(title):
    record = {
        "source": "greenhouse",
        "title_raw": title,
        "description_raw": "",
    }

    priority, _ = classify_candidate(record)

    assert priority == "high_priority"


def test_hn_relevant_role():
    record = {
        "source": "hackernews",
        "title_raw": None,
        "description_raw": (
            "ExampleCorp | Senior Data Engineer | "
            "Remote US | Full-time. "
            "We are hiring a data engineer."
        ),
    }

    priority, _ = classify_candidate(record)

    assert priority == "high_priority"


def test_hn_multiple_roles():
    record = {
        "source": "hackernews",
        "title_raw": None,
        "description_raw": (
            "ExampleCorp | Multiple Engineering Roles | "
            "Remote US. We are hiring across teams."
        ),
    }

    priority, _ = classify_candidate(record)

    assert priority == "needs_review"


def test_hn_unrelated_role():
    record = {
        "source": "hackernews",
        "title_raw": None,
        "description_raw": (
            "ExampleCorp | Java Developer | "
            "New York | Full-time. "
            "We build enterprise applications."
        ),
    }

    priority, _ = classify_candidate(record)

    assert priority == "low_priority"


def test_hn_ambiguous_role():
    record = {
        "source": "hackernews",
        "title_raw": None,
        "description_raw": (
            "ExampleCorp | Founding Engineer | "
            "San Francisco | Full-time. "
            "We build modern software infrastructure."
        ),
    }

    priority, _ = classify_candidate(record)

    assert priority == "needs_review"
