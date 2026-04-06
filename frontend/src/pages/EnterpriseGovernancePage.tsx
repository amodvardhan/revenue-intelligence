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
      <div className="p-8">
        <p className="text-slate-600">Enable VITE_ENABLE_PHASE6 to use Enterprise governance.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8 p-8">
      <div>
        <h1 className="text-display text-2xl font-semibold text-slate-900">Enterprise governance</h1>
        <p className="mt-2 text-sm text-slate-600">
          SSO configuration, audit export, and operational health — Phase 6.
        </p>
      </div>

      <section className="rounded-lg border border-border bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Security &amp; visibility</h2>
        {security.isLoading ? (
          <p className="text-sm text-slate-500">Loading…</p>
        ) : security.data ? (
          <dl className="mt-4 grid gap-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-600">Reporting currency</dt>
              <dd className="font-medium">{security.data.reporting_currency_code}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-600">Invite only</dt>
              <dd>{security.data.invite_only ? "Yes" : "No"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-600">Require SSO (standard users)</dt>
              <dd>{security.data.require_sso_for_standard_users ? "Yes" : "No"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-600">OIDC enabled</dt>
              <dd>{security.data.sso_oidc_enabled ? "Yes" : "No"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-600">SAML enabled</dt>
              <dd>{security.data.sso_saml_enabled ? "Yes" : "No"}</dd>
            </div>
            <p className="mt-2 text-xs text-slate-500">{security.data.retention_notice_label}</p>
          </dl>
        ) : null}
      </section>

      <section className="rounded-lg border border-border bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">OIDC (non-secret fields)</h2>
        <p className="mt-1 text-xs text-slate-500">Client secret stays in server environment (OIDC_CLIENT_SECRET).</p>
        <div className="mt-4 space-y-3">
          <div>
            <label className="text-sm font-medium text-slate-700">Issuer URL</label>
            <input
              className="mt-1 w-full rounded-md border border-border px-3 py-2 text-sm"
              value={issuer}
              placeholder={ssoConfig.data?.oidc?.oidc_issuer ?? ""}
              onChange={(e) => setIssuer(e.target.value)}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700">Client ID</label>
            <input
              className="mt-1 w-full rounded-md border border-border px-3 py-2 text-sm"
              value={clientId}
              placeholder={ssoConfig.data?.oidc?.oidc_client_id ?? ""}
              onChange={(e) => setClientId(e.target.value)}
            />
          </div>
          {ssoConfig.data?.oidc_redirect_uri_readonly ? (
            <p className="text-xs text-slate-500">
              Redirect URI (read-only): {ssoConfig.data.oidc_redirect_uri_readonly}
            </p>
          ) : null}
          <button
            type="button"
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white"
            disabled={saveOidc.isPending}
            onClick={() => saveOidc.mutate()}
          >
            {saveOidc.isPending ? "Saving…" : "Save OIDC"}
          </button>
        </div>
      </section>

      <section className="rounded-lg border border-border bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">SAML metadata</h2>
        <div className="mt-4 space-y-3">
          <input
            className="w-full rounded-md border border-border px-3 py-2 text-sm"
            value={metadataUrl}
            placeholder={ssoConfig.data?.saml?.saml_metadata_url ?? "https://idp.example/metadata"}
            onChange={(e) => setMetadataUrl(e.target.value)}
          />
          {ssoConfig.data?.saml_acs_url_readonly ? (
            <p className="text-xs text-slate-500">ACS URL: {ssoConfig.data.saml_acs_url_readonly}</p>
          ) : null}
          <button
            type="button"
            className="rounded-md border border-border px-4 py-2 text-sm"
            disabled={saveSaml.isPending}
            onClick={() => saveSaml.mutate()}
          >
            {saveSaml.isPending ? "Saving…" : "Save SAML"}
          </button>
        </div>
      </section>

      <section className="rounded-lg border border-border bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Approved email domains</h2>
        <div className="mt-3 flex gap-2">
          <input
            className="flex-1 rounded-md border border-border px-3 py-2 text-sm"
            value={domainInput}
            placeholder="example.com"
            onChange={(e) => setDomainInput(e.target.value)}
          />
          <button
            type="button"
            className="rounded-md bg-primary px-3 py-2 text-sm text-white"
            disabled={addDomain.isPending}
            onClick={() => domainInput && addDomain.mutate(domainInput)}
          >
            Add
          </button>
        </div>
        <ul className="mt-3 text-sm text-slate-700">
          {allowlist.data?.map((d) => (
            <li key={d.allowlist_id}>{d.email_domain}</li>
          ))}
        </ul>
      </section>

      <section className="rounded-lg border border-border bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Audit export</h2>
        <p className="mt-1 text-xs text-slate-500">
          Requires audit export permission. Operational retention default 365 days — narrow the window as needed.
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <div>
            <label className="text-sm text-slate-700">From (ISO)</label>
            <input
              className="mt-1 w-full rounded-md border border-border px-3 py-2 text-sm"
              value={exportFrom}
              onChange={(e) => setExportFrom(e.target.value)}
            />
          </div>
          <div>
            <label className="text-sm text-slate-700">To (ISO)</label>
            <input
              className="mt-1 w-full rounded-md border border-border px-3 py-2 text-sm"
              value={exportTo}
              onChange={(e) => setExportTo(e.target.value)}
            />
          </div>
        </div>
        <button
          type="button"
          className="mt-4 rounded-md bg-primary px-4 py-2 text-sm font-medium text-white"
          disabled={auditExport.isPending}
          onClick={() => auditExport.mutate()}
        >
          {auditExport.isPending ? "Exporting…" : "Download CSV"}
        </button>
      </section>

      <section className="rounded-lg border border-border bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Operational health</h2>
        <pre className="mt-3 max-h-64 overflow-auto rounded-md bg-slate-50 p-3 text-xs">
          {ops.data ? JSON.stringify(ops.data, null, 2) : "Loading…"}
        </pre>
      </section>
    </div>
  );
}
