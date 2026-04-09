import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api } from "@/services/api";

interface OrgList {
  items: Array<{ org_id: string; org_name: string }>;
}

interface CustomerItem {
  customer_id: string;
  customer_name: string;
  customer_name_common: string | null;
  customer_code: string | null;
}

export function CustomersPage() {
  const queryClient = useQueryClient();
  const [orgId, setOrgId] = useState("");
  const [legalName, setLegalName] = useState("");
  const [commonName, setCommonName] = useState("");
  const [code, setCode] = useState("");
  const [banner, setBanner] = useState<string | null>(null);

  const orgs = useQuery({
    queryKey: ["organizations"],
    queryFn: async () => {
      const { data } = await api.get<OrgList>("/api/v1/organizations");
      return data;
    },
  });

  const firstOrg = orgs.data?.items[0]?.org_id;
  useEffect(() => {
    if (firstOrg && !orgId) setOrgId(firstOrg);
  }, [firstOrg, orgId]);

  const customers = useQuery({
    queryKey: ["customers", orgId],
    queryFn: async () => {
      const { data } = await api.get<{ items: CustomerItem[] }>("/api/v1/customers", {
        params: { org_id: orgId },
      });
      return data;
    },
    enabled: Boolean(orgId),
    retry: false,
  });

  const createCustomer = useMutation({
    mutationFn: async () => {
      const { data } = await api.post<CustomerItem>("/api/v1/customers", {
        org_id: orgId,
        customer_name: legalName.trim(),
        customer_name_common: commonName.trim() || null,
        customer_code: code.trim() || null,
      });
      return data;
    },
    onSuccess: () => {
      setBanner(null);
      setLegalName("");
      setCommonName("");
      setCode("");
      void queryClient.invalidateQueries({ queryKey: ["customers", orgId] });
    },
    onError: () => {
      setBanner(
        "Could not create customer. Check permissions (Admin, IT Admin, Finance, or BU head), or a duplicate customer code.",
      );
    },
  });

  return (
    <div className="page-shell page-shell--md">
      <header className="page-header-block">
        <h1 className="page-headline">Customers</h1>
        <p className="page-lede">
          Create customers under an organization before you assign delivery managers, attach projects, or load revenue.
          Imports can still add or update customers from Excel; manual rows here keep operations moving when spreadsheets are
          not ready.
        </p>
      </header>

      {customers.isError ? (
        <div className="rounded-xl border border-neutral-200 bg-neutral-50 px-4 py-3 text-sm text-neutral-800" role="status">
          Could not load customers. Ensure you have access to the organization.
        </div>
      ) : null}

      {orgId ? (
        <div className="surface-card space-y-4 p-6">
          <h2 className="text-heading text-[15px]">New customer</h2>
          {banner ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50/90 px-3 py-2 text-sm text-amber-950">{banner}</div>
          ) : null}
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <label className="form-field-label">Organization</label>
              <select
                className="input-modern !h-10 w-full"
                value={orgId}
                onChange={(e) => setOrgId(e.target.value)}
                disabled={orgs.isLoading}
              >
                {orgs.data?.items.map((o) => (
                  <option key={o.org_id} value={o.org_id}>
                    {o.org_name}
                  </option>
                ))}
              </select>
            </div>
            <div className="sm:col-span-2">
              <label className="form-field-label">Legal name</label>
              <input
                className="input-modern !h-10 w-full"
                value={legalName}
                onChange={(e) => setLegalName(e.target.value)}
                placeholder="Registered entity name"
              />
            </div>
            <div>
              <label className="form-field-label">Common name (optional)</label>
              <input
                className="input-modern !h-10 w-full"
                value={commonName}
                onChange={(e) => setCommonName(e.target.value)}
                placeholder="Short display name"
              />
            </div>
            <div>
              <label className="form-field-label">Code (optional)</label>
              <input
                className="input-modern !h-10 w-full"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="Unique in tenant when set"
              />
            </div>
          </div>
          <button
            type="button"
            className="h-10 rounded-[10px] bg-primary px-5 text-sm font-medium text-white transition-colors hover:bg-primary/90 focus-visible:outline focus-visible:ring-2 focus-visible:ring-primary/35 disabled:opacity-50"
            disabled={!legalName.trim() || createCustomer.isPending}
            onClick={() => {
              setBanner(null);
              createCustomer.mutate();
            }}
          >
            Create customer
          </button>
        </div>
      ) : null}

      {customers.isSuccess ? (
        <div className="overflow-x-auto rounded-2xl border border-border/60 bg-white shadow-card">
          <table className="min-w-full divide-y divide-border text-sm">
            <thead className="bg-surface-subtle/80 text-left text-xs font-semibold text-ink">
              <tr>
                <th className="px-4 py-3">Legal name</th>
                <th className="px-4 py-3">Common name</th>
                <th className="px-4 py-3">Code</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {customers.data.items.length === 0 ? (
                <tr>
                  <td className="px-4 py-8 text-center text-ink-muted" colSpan={3}>
                    No customers yet for this organization.
                  </td>
                </tr>
              ) : (
                customers.data.items.map((c) => (
                  <tr key={c.customer_id} className="hover:bg-neutral-50/80">
                    <td className="px-4 py-3 text-ink">{c.customer_name}</td>
                    <td className="px-4 py-3 text-ink-muted">{c.customer_name_common ?? "—"}</td>
                    <td className="px-4 py-3 font-mono text-xs text-ink-muted">{c.customer_code ?? "—"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      ) : null}

      {customers.isLoading ? <p className="text-sm text-ink-muted">Loading…</p> : null}
    </div>
  );
}
