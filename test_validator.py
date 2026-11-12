
from pipeline.schemas import JobExtraction
from pipeline.validator import validate_job

source_text = """
Company: Stripe
Title: Senior Data Engineer
Location: San Francisco, US
Description: We are hiring a Senior Data Engineer.
Required skills include Python, SQL and Spark.
"""

job = JobExtraction(
    company="Stripe",
    title="Senior Data Engineer",
    seniority="senior",
    city="San Francisco",
    country="US",
    skills=["Python", "SQL", "Spark"],
    evidence={
        "company": "Stripe",
        "title": "Senior Data Engineer",
        "seniority": "Senior Data Engineer",
        "city": "San Francisco",
        "country": "US"
    }
)

validated_job, warnings = validate_job(
    job,
    source_text
)

print("\nVALIDATED JOB:")

if validated_job:
    print(validated_job.model_dump_json(indent=2))
else:
    print("Job rejected")

print("\nWARNINGS:")
print(warnings)
