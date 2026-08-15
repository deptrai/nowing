"""Default field mapping for CRM providers."""

from __future__ import annotations

DEFAULT_FIELD_MAPPINGS: dict[str, dict[str, str]] = {
    "salesforce": {
        "company_name": "Company",
        "domain": "Website",
        "industry": "Industry",
        "company_size": "NumberOfEmployees",
        "location": "City",
        "email": "Email",
        "phone": "Phone",
        "title": "Title",
        "name": "FirstName",
        "last_name": "LastName",
        "fit_score": "nowing_fit_score__c",
        "intent_score": "nowing_intent_score__c",
        "composite_score": "nowing_composite_score__c",
    },
    "hubspot": {
        "company_name": "company",
        "domain": "website",
        "industry": "industry",
        "company_size": "num_employees",
        "location": "city",
        "email": "email",
        "phone": "phone",
        "title": "jobtitle",
        "name": "firstname",
        "last_name": "lastname",
        "fit_score": "nowing_fit_score",
        "intent_score": "nowing_intent_score",
        "composite_score": "nowing_composite_score",
    },
    "pipedrive": {
        "company_name": "org_id.name",
        "domain": "org_id.email",
        "industry": "org_id.bf0812a2a5b95bee13fac53f50f9e9c68a5c3846",
        "company_size": "org_id.people_count",
        "location": "org_id.address",
        "email": "email",
        "phone": "phone",
        "title": "job_title",
        "name": "name",
        "last_name": "",
        "fit_score": "nowing_fit_score",
        "intent_score": "nowing_intent_score",
        "composite_score": "nowing_composite_score",
    },
}


def get_field_mapping(
    provider: str, overrides: dict[str, str] | None
) -> dict[str, str]:
    """Return merged field mapping for a provider."""
    mapping = DEFAULT_FIELD_MAPPINGS.get(provider, {}).copy()
    if overrides:
        mapping.update(overrides)
    return mapping
