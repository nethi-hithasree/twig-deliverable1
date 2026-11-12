from pipeline.filters import is_relevant_title, is_us_or_us_remote, is_hn_candidate

def test_relevant_titles():
    assert is_relevant_title("Senior Data Engineer")
    assert is_relevant_title("Machine Learning Engineer")
    assert is_relevant_title("Analytics Engineer")
    assert not is_relevant_title("Product Manager")

def test_us_location_and_remote():
    assert is_us_or_us_remote("New York, NY")
    assert is_us_or_us_remote("US Remote")
    assert not is_us_or_us_remote("London, UK")

def test_hn_candidate_is_broad():
    assert is_hn_candidate("We are hiring a Senior Data Engineer in San Francisco, CA")
    assert not is_hn_candidate("We are hiring a Sales Manager in London")
