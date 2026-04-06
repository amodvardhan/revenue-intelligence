"""HubSpot API constants."""

HUBSPOT_AUTH_BASE = "https://app.hubspot.com/oauth/authorize"
HUBSPOT_API_BASE = "https://api.hubapi.com"

# Least-privilege scopes for deals + company associations (v1).
DEFAULT_SCOPES = "oauth crm.objects.deals.read crm.objects.companies.read"

DEAL_PROPERTIES = (
    "dealname",
    "amount",
    "closedate",
    "pipeline",
    "dealstage",
    "hs_lastmodifieddate",
    "hs_object_id",
)
