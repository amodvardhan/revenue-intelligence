import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "@/services/api";

const phase6 = import.meta.env.VITE_ENABLE_PHASE6 === "true";

type TenantSecurity = {
  tenant_id: string;
  reporting_currency_code: string;
  invite_only: boolean;
  require_sso_for_standard_users: boolean;
  sso_oidc_enabled: boolean;
  sso_saml_enabled: boolean;
  retention_notice_label: string | null;
};

type SsoBundle = {
  tenant_id: string;
  oidc: {
    sso_provider_id: string | null;
    is_enabled: boolean;
    oidc_issuer: string | null;
    oidc_client_id: string | null;
  } | null;
  saml: {
    sso_provider_id: string | null;
    is_enabled: boolean;
    saml_metadata_url: string | null;
    saml_entity_id: string | null;
  } | null;
  oidc_redirect_uri_readonly: string;
  saml_acs_url_readonly: string;
};

export function EnterpriseGovernancePage() {
  const qc = useQueryClient();
  const [issuer, setIssuer] = useState("");
  const [clientId, setClientId] = useState("");
  const [metadataUrl, setMetadataUrl] = useState("");
  const [domainInput, setDomainInput] = useState("");
  const [exportFrom, setExportFrom] = useState("2026-01-01T00:00:00Z");
  const [exportTo, setExportTo] = useState("2026-12-31T23:59:59Z");

  const security = useQuery({
    queryKey: ["tenant-security"],
    queryFn: async () => {
      const { data } = await api.get<TenantSecurity>("/api/v1/tenant/security");
      return data;
    },
    enabled: phase6,
  });

  const ssoConfig = useQuery({
    queryKey: ["sso-configuration"],
    queryFn: async () => {
      const { data } = await api.get<SsoBundle>("/api/v1/tenant/sso/configuration");
      return data;
    },
    enabled: phase6,
  });

  const allowlist = useQuery({
    queryKey: ["domain-allowlist"],
    queryFn: async () => {
      const { data } = await api.get<{ items: { allowlist_id: string; email_domain: string }[] }>(
        "/api/v1/tenant/sso/domain-allowlist",
      );
      return data.items;
    },
    enabled: phase6,
  });

  const ops = useQuery({
    queryKey: ["operations-summary"],
    queryFn: async () => {
      const { data } = await api.get("/api/v1/admin/operations/summary");
      return data;
    },
    enabled: phase6,
  });

  const saveOidc = useMutation({
    mutationFn: async () => {
      await api.put("/api/v1/tenant/sso/configuration", {
        protocol: "oidc",
        is_enabled: true,
        oidc_issuer: issuer || ssoConfig.data?.oidc?.oidc_issuer,
        oidc_client_id: clientId || ssoConfig.data?.oidc?.oidc_client_id,
      });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["sso-configuration"] });
    },
  });

  const saveSaml = useMutation({
    mutationFn: async () => {
      await api.put("/api/v1/tenant/sso/configuration", {
        protocol: "saml",
        is_enabled: true,
        saml_metadata_url: metadataUrl || ssoConfig.data?.saml?.saml_metadata_url,
      });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["sso-configuration"] });
    },
  });

  const addDomain = useMutation({
    mutationFn: async (email_domain: string) => {
      await api.post("/api/v1/tenant/sso/domain-allowlist", { email_domain });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["domain-allowlist"] });
      setDomainInput("");
    },
  });

  const auditExport = useMutation({
    mutationFn: async () => {
      const res = await api.post(
        "/api/v1/audit/exports",
        {
          event_families: ["ingestion", "nl_query", "hubspot_sync", "sso_security"],
          created_from: exportFrom,
          created_to: exportTo,
          format: "csv",
        },
        { responseType: "blob" },
      );
      const blob = new Blob([res.data], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "audit-export.csv";
      a.click();
      URL.revokeObjectURL(url);
    },
  });

  if (!phase6) {
    return (
      <div className="page-shell page-shell--narrow page-shell--tight">
        <p className="text-ink-muted">Enable VITE_ENABLE_PHASE6 to use Enterprise governance.</p>
      </div>
    );
  }

  return (
    <div className="page-shell page-shell--narrow">
      <header className="page-header-block">
        <h1 className="page-headline">Enterprise governance</h1>
        <p className="page-lede">
          SSO configuration, audit export, and operational health — Phase 6.
        </p>
      </header>

      <section className="surface-card p-6">
        <h2 className="text-heading">Security &amp; visibility</h2>
        {security.isLoading ? (
          <p className="text-sm text-ink-muted">Loading…</p>
        ) : security.data ? (
          <dl className="mt-4 grid gap-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-ink-muted">Reporting currency</dt>
              <dd className="font-medium">{security.data.reporting_currency_code}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-ink-muted">Invite only</dt>
              <dd>{security.data.invite_only ? "Yes" : "No"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-ink-muted">Require SSO (standard users)</dt>
              <dd>{security.data.require_sso_for_standard_users ? "Yes" : "No"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-ink-muted">OIDC enabled</dt>
              <dd>{security.data.sso_oidc_enabled ? "Yes" : "No"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-ink-muted">SAML enabled</dt>
              <dd>{security.data.sso_saml_enabled ? "Yes" : "No"}</dd>
            </div>
            <p className="mt-2 text-xs text-ink-muted">{security.data.retention_notice_label}</p>
          </dl>
        ) : null}
      </section>

      <section className="surface-card p-6">
        <h2 className="text-heading">OIDC (non-secret fields)</h2>
        <p className="mt-1 text-xs text-ink-muted">Client secret stays in server environment (OIDC_CLIENT_SECRET).</p>
        <div className="mt-4 space-y-3">
          <div>
            <label className="form-field-label">Issuer URL</label>
            <input
              className="input-modern mt-1 w-full !h-10 text-sm"
              value={issuer}
              placeholder={ssoConfig.data?.oidc?.oidc_issuer ?? ""}
              onChange={(e) => setIssuer(e.target.value)}
            />
          </div>
          <div>
            <label className="form-field-label">Client ID</label>
            <input
              className="input-modern mt-1 w-full !h-10 text-sm"
              value={clientId}
              placeholder={ssoConfig.data?.oidc?.oidc_client_id ?? ""}
              onChange={(e) => setClientId(e.target.value)}
            />
          </div>
          {ssoConfig.data?.oidc_redirect_uri_readonly ? (
            <p className="text-xs text-ink-muted">
              Redirect URI (read-only): {ssoConfig.data.oidc_redirect_uri_readonly}
            </p>
          ) : null}
          <button
            type="button"
            className="btn-primary-solid px-4 text-sm"
            disabled={saveOidc.isPending}
            onClick={() => saveOidc.mutate()}
          >
            {saveOidc.isPending ? "Saving…" : "Save OIDC"}
          </button>
        </div>
      </section>

      <section className="surface-card p-6">
        <h2 className="text-heading">SAML metadata</h2>
        <div className="mt-4 space-y-3">
          <input
            className="input-modern w-full !h-10 text-sm"
            value={metadataUrl}
            placeholder={ssoConfig.data?.saml?.saml_metadata_url ?? "https://idp.example/metadata"}
            onChange={(e) => setMetadataUrl(e.target.value)}
          />
          {ssoConfig.data?.saml_acs_url_readonly ? (
            <p className="text-xs text-ink-muted">ACS URL: {ssoConfig.data.saml_acs_url_readonly}</p>
          ) : null}
          <button
            type="button"
            className="btn-secondary-solid px-4 text-sm"
            disabled={saveSaml.isPending}
            onClick={() => saveSaml.mutate()}
          >
            {saveSaml.isPending ? "Saving…" : "Save SAML"}
          </button>
        </div>
      </section>

      <section className="surface-card p-6">
        <h2 className="text-heading">Approved email domains</h2>
        <div className="mt-3 flex gap-2">
          <input
            className="input-modern min-w-0 flex-1 !h-10 text-sm"
            value={domainInput}
            placeholder="example.com"
            onChange={(e) => setDomainInput(e.target.value)}
          />
          <button
            type="button"
            className="btn-primary-solid shrink-0 px-4 text-sm"
            disabled={addDomain.isPending}
            onClick={() => domainInput && addDomain.mutate(domainInput)}
          >
            Add
          </button>
        </div>
        <ul className="mt-3 text-sm text-ink">
          {allowlist.data?.map((d) => (
            <li key={d.allowlist_id}>{d.email_domain}</li>
          ))}
        </ul>
      </section>

      <section className="surface-card p-6">
        <h2 className="text-heading">Audit export</h2>
        <p className="mt-1 text-xs text-ink-muted">
          Requires audit export permission. Operational retention default 365 days — narrow the window as needed.
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <div>
            <label className="form-field-label">From (ISO)</label>
            <input
              className="input-modern mt-1 w-full !h-10 text-sm font-mono"
              value={exportFrom}
              onChange={(e) => setExportFrom(e.target.value)}
            />
          </div>
          <div>
            <label className="form-field-label">To (ISO)</label>
            <input
              className="input-modern mt-1 w-full !h-10 text-sm font-mono"
              value={exportTo}
              onChange={(e) => setExportTo(e.target.value)}
            />
          </div>
        </div>
        <button
          type="button"
          className="btn-primary-solid mt-4 px-4 text-sm"
          disabled={auditExport.isPending}
          onClick={() => auditExport.mutate()}
        >
          {auditExport.isPending ? "Exporting…" : "Download CSV"}
        </button>
      </section>

      <section className="surface-card p-6">
        <h2 className="text-heading">Operational health</h2>
        <pre className="surface-card-quiet mt-3 max-h-64 overflow-auto p-4 font-mono text-xs text-ink">
          {ops.data ? JSON.stringify(ops.data, null, 2) : "Loading…"}
        </pre>
      </section>
    </div>
  );
}
