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
  business_unit_id: string | null;
  business_unit_name: string | null;
  division_id: string | null;
  division_name: string | null;
}

function CustomerHierarchyRow({
  orgId,
  customer,
}: {
  orgId: string;
  customer: CustomerItem;
}) {
  const queryClient = useQueryClient();
  const [bu, setBu] = useState(customer.business_unit_id ?? "");
  const [div, setDiv] = useState(customer.division_id ?? "");

  useEffect(() => {
    setBu(customer.business_unit_id ?? "");
    setDiv(customer.division_id ?? "");
  }, [customer.customer_id, customer.business_unit_id, customer.division_id]);

  const businessUnits = useQuery({
    queryKey: ["business-units", orgId],
    queryFn: async () => {
      const { data } = await api.get<{ items: { business_unit_id: string; business_unit_name: string }[] }>(
        "/api/v1/business-units",
        { params: { org_id: orgId } },
      );
      return data;
    },
    enabled: Boolean(orgId),
  });

  const divisions = useQuery({
    queryKey: ["divisions", bu],
    queryFn: async () => {
      const { data } = await api.get<{ items: { division_id: string; division_name: string }[] }>("/api/v1/divisions", {
        params: { business_unit_id: bu },
      });
      return data;
    },
    enabled: Boolean(bu),
  });

  const patchHierarchy = useMutation({
    mutationFn: async (payload: { business_unit_id: string | null; division_id: string | null }) => {
      const { data } = await api.patch<CustomerItem>(`/api/v1/customers/${customer.customer_id}`, payload);
      return data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["customers", orgId] });
    },
  });

  return (
    <tr key={customer.customer_id} className="hover:bg-neutral-50/80">
      <td className="px-4 py-3 text-ink">{customer.customer_name}</td>
      <td className="px-4 py-3 text-ink-muted">{customer.customer_name_common ?? "—"}</td>
      <td className="px-4 py-3 font-mono text-xs text-ink-muted">{customer.customer_code ?? "—"}</td>
      <td className="px-4 py-2">
        <select
          className="input-modern !h-9 w-full min-w-[10rem] text-[13px]"
          value={bu}
          disabled={businessUnits.isLoading || patchHierarchy.isPending}
          onChange={(e) => {
            const v = e.target.value;
            setBu(v);
            setDiv("");
            patchHierarchy.mutate({ business_unit_id: v || null, division_id: null });
          }}
          aria-label={`Business unit for ${customer.customer_name}`}
        >
          <option value="">—</option>
          {businessUnits.data?.items.map((b) => (
            <option key={b.business_unit_id} value={b.business_unit_id}>
              {b.business_unit_name}
            </option>
          ))}
        </select>
      </td>
      <td className="px-4 py-2">
        <select
          className="input-modern !h-9 w-full min-w-[10rem] text-[13px]"
          value={div}
          disabled={!bu || divisions.isLoading || patchHierarchy.isPending}
          onChange={(e) => {
            const v = e.target.value;
            setDiv(v);
            patchHierarchy.mutate({ business_unit_id: bu || null, division_id: v || null });
          }}
          aria-label={`Division for ${customer.customer_name}`}
        >
          <option value="">—</option>
          {divisions.data?.items.map((d) => (
            <option key={d.division_id} value={d.division_id}>
              {d.division_name}
            </option>
          ))}
        </select>
      </td>
    </tr>
  );
}

export function CustomersPage() {
  const queryClient = useQueryClient();
  const [orgId, setOrgId] = useState("");
  const [legalName, setLegalName] = useState("");
  const [commonName, setCommonName] = useState("");
  const [code, setCode] = useState("");
  const [newBu, setNewBu] = useState("");
  const [newDiv, setNewDiv] = useState("");
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

  useEffect(() => {
    setNewBu("");
    setNewDiv("");
  }, [orgId]);

  useEffect(() => {
    setNewDiv("");
  }, [newBu]);

  const businessUnits = useQuery({
    queryKey: ["business-units", orgId],
    queryFn: async () => {
      const { data } = await api.get<{ items: { business_unit_id: string; business_unit_name: string }[] }>(
        "/api/v1/business-units",
        { params: { org_id: orgId } },
      );
      return data;
    },
    enabled: Boolean(orgId),
  });

  const newDivisions = useQuery({
    queryKey: ["divisions", newBu],
    queryFn: async () => {
      const { data } = await api.get<{ items: { division_id: string; division_name: string }[] }>("/api/v1/divisions", {
        params: { business_unit_id: newBu },
      });
      return data;
    },
    enabled: Boolean(newBu),
  });

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
        business_unit_id: newBu || null,
        division_id: newDiv || null,
      });
      return data;
    },
    onSuccess: () => {
      setBanner(null);
      setLegalName("");
      setCommonName("");
      setCode("");
      setNewBu("");
      setNewDiv("");
      void queryClient.invalidateQueries({ queryKey: ["customers", orgId] });
    },
    onError: () => {
      setBanner(
        "Could not create customer. Check permissions (Admin, IT Admin, Finance, or BU head), hierarchy (BU must belong to this org), or a duplicate customer code.",
      );
    },
  });

  return (
    <div className="page-shell page-shell--md">
      <header className="page-header-block">
        <h1 className="page-headline">Customers</h1>
        <p className="page-lede">
          Create customers under an organization before you assign delivery managers, attach projects, or load revenue.
          Assign each account to a business unit (and optionally a division) so revenue rollups and the Revenue matrix
          can narrow by commercial hierarchy even when fact rows omit BU or division.
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
            <div>
              <label className="form-field-label">Business unit (optional)</label>
              <select
                className="input-modern !h-10 w-full"
                value={newBu}
                onChange={(e) => setNewBu(e.target.value)}
                disabled={!orgId || businessUnits.isLoading}
              >
                <option value="">—</option>
                {businessUnits.data?.items.map((b) => (
                  <option key={b.business_unit_id} value={b.business_unit_id}>
                    {b.business_unit_name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="form-field-label">Division (optional)</label>
              <select
                className="input-modern !h-10 w-full"
                value={newDiv}
                onChange={(e) => setNewDiv(e.target.value)}
                disabled={!newBu || newDivisions.isLoading}
              >
                <option value="">—</option>
                {newDivisions.data?.items.map((d) => (
                  <option key={d.division_id} value={d.division_id}>
                    {d.division_name}
                  </option>
                ))}
              </select>
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
                <th className="px-4 py-3">Business unit</th>
                <th className="px-4 py-3">Division</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {customers.data.items.length === 0 ? (
                <tr>
                  <td className="px-4 py-8 text-center text-ink-muted" colSpan={5}>
                    No customers yet for this organization.
                  </td>
                </tr>
              ) : (
                customers.data.items.map((c) => <CustomerHierarchyRow key={c.customer_id} orgId={orgId} customer={c} />)
              )}
            </tbody>
          </table>
        </div>
      ) : null}

      {customers.isLoading ? <p className="text-sm text-ink-muted">Loading…</p> : null}
    </div>
  );
}
