"""SQLAlchemy ORM models — import for metadata registration and Alembic."""

from app.models.nl_semantic import NlQuerySession, SemanticLayerVersion
from app.models.audit import AuditEvent, QueryAuditLog
from app.models.dimensions import (
    DimBusinessUnit,
    DimCustomer,
    DimDivision,
    DimOrganization,
    DimRevenueType,
    UserBusinessUnitAccess,
    UserOrgRole,
)
from app.models.phase5 import (
    CostAllocationRule,
    FactCost,
    FactForecast,
    ForecastSeries,
    FxRate,
    SegmentDefinition,
    SegmentMembership,
)
from app.models.facts import AnalyticsRefreshMetadata, FactRevenue, IngestionBatch
from app.models.hubspot_integration import (
    HubspotConnection,
    HubspotDealStaging,
    HubspotIdMapping,
    HubspotSyncCursor,
    IntegrationSyncRun,
    RevenueSourceConflict,
)
from app.models.phase6_governance import (
    IdpGroupRoleMapping,
    SsoProviderConfig,
    TenantEmailDomainAllowlist,
    TenantSecuritySettings,
    UserFederatedIdentity,
    UserPermission,
)
from app.models.phase7 import (
    NotificationOutbox,
    RevenueVarianceCase,
    RevenueVarianceExplanation,
    VarianceDetectionRule,
    WorkbookTemplateVersion,
)
from app.models.tenant import Tenant, User

__all__ = [
    "AnalyticsRefreshMetadata",
    "AuditEvent",
    "DimBusinessUnit",
    "DimCustomer",
    "DimDivision",
    "DimOrganization",
    "DimRevenueType",
    "FactRevenue",
    "HubspotConnection",
    "HubspotDealStaging",
    "HubspotIdMapping",
    "HubspotSyncCursor",
    "IngestionBatch",
    "IntegrationSyncRun",
    "RevenueSourceConflict",
    "NlQuerySession",
    "QueryAuditLog",
    "SemanticLayerVersion",
    "Tenant",
    "User",
    "UserBusinessUnitAccess",
    "UserOrgRole",
    "FxRate",
    "ForecastSeries",
    "FactForecast",
    "FactCost",
    "CostAllocationRule",
    "SegmentDefinition",
    "SegmentMembership",
    "SsoProviderConfig",
    "TenantEmailDomainAllowlist",
    "UserFederatedIdentity",
    "IdpGroupRoleMapping",
    "UserPermission",
    "TenantSecuritySettings",
    "VarianceDetectionRule",
    "RevenueVarianceCase",
    "RevenueVarianceExplanation",
    "WorkbookTemplateVersion",
    "NotificationOutbox",
]
