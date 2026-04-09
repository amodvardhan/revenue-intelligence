import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api } from "@/services/api";

interface OrgList {
  items: Array<{ org_id: string; org_name: string }>;
}

interface CustomerRef {
  customer_id: string;
  customer_name: string;
}

interface TenantUserItem {
  user_id: string;
  email: string;
}

interface AssignmentRow {
  assignment_id: string;
  org_id: string;
  customer_id: string;
  customer_legal: string;
  delivery_manager_user_id: string;
  delivery_manager_email: string;
  valid_from: string;
}

export function DeliveryManagersPage() {
  const queryClient = useQueryClient();
  const [orgId, setOrgId] = useState("");
  const [assignCustomerId, setAssignCustomerId] = useState("");
  const [assignUserId, setAssignUserId] = useState("");
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
      const { data } = await api.get<{ items: CustomerRef[] }>("/api/v1/customers", {
        params: { org_id: orgId },
      });
      return data;
    },
    enabled: Boolean(orgId),
  });

  const tenantUsers = useQuery({
    queryKey: ["tenant-users"],
    queryFn: async () => {
      const { data } = await api.get<{ items: TenantUserItem[] }>("/api/v1/delivery-managers/tenant-users");
      return data;
    },
  });

  const assignments = useQuery({
    queryKey: ["dm-assignments", orgId],
    queryFn: async () => {
      const { data } = await api.get<{ items: AssignmentRow[] }>("/api/v1/delivery-managers/assignments", {
        params: { org_id: orgId },
      });
      return data;
    },
    enabled: Boolean(orgId),
  });

  const assign = useMutation({
    mutationFn: async () => {
      const { data } = await api.put<AssignmentRow>("/api/v1/delivery-managers/assignments", {
        org_id: orgId,
        customer_id: assignCustomerId,
        delivery_manager_user_id: assignUserId,
      });
      return data;
    },
    onSuccess: () => {
      setBanner(null);
      void queryClient.invalidateQueries({ queryKey: ["dm-assignments", orgId] });
    },
    onError: () => {
      setBanner("Could not save assignment. Check permissions and selections.");
    },
  });

  return (
    <div className="mx-auto max-w-5xl space-y-8 px-6 py-10">
      <header className="border-b border-black/[0.06] pb-8">
        <h1 className="page-headline">Delivery managers</h1>
        <p className="page-lede">
          Map each customer to a directory user (delivery manager). Replacing a DM closes the previous assignment; revenue
          data stays with the customer and is attributed to the current DM for operations.
        </p>
      </header>

      <div className="surface-card flex flex-wrap items-end gap-4 p-5">
        <div className="min-w-[220px]">
          <label className="small-caps-label mb-1.5 block">Organization</label>
          <select
            className="input-modern !h-10 w-full"
            value={orgId}
            onChange={(e) => setOrgId(e.target.value)}
            disabled={orgs.isLoading}
          >
            <option value="">Select organization</option>
            {orgs.data?.items.map((o) => (
              <option key={o.org_id} value={o.org_id}>
                {o.org_name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {banner ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50/90 px-4 py-3 text-sm text-amber-950" role="status">
          {banner}
        </div>
      ) : null}

      {orgId ? (
        <div className="surface-card space-y-4 p-6">
          <h2 className="text-sm font-semibold text-ink">Assign or change DM</h2>
          <div className="flex flex-wrap items-end gap-4">
            <div className="min-w-[220px] flex-1">
              <label className="small-caps-label mb-1.5 block">Customer</label>
              <select
                className="input-modern !h-10 w-full"
                value={assignCustomerId}
                onChange={(e) => setAssignCustomerId(e.target.value)}
                disabled={customers.isLoading}
              >
                <option value="">Select customer</option>
                {customers.data?.items.map((c) => (
                  <option key={c.customer_id} value={c.customer_id}>
                    {c.customer_name}
                  </option>
                ))}
              </select>
            </div>
            <div className="min-w-[220px] flex-1">
              <label className="small-caps-label mb-1.5 block">Delivery manager (user)</label>
              <select
                className="input-modern !h-10 w-full"
                value={assignUserId}
                onChange={(e) => setAssignUserId(e.target.value)}
                disabled={tenantUsers.isLoading}
              >
                <option value="">Select user</option>
                {tenantUsers.data?.items.map((u) => (
                  <option key={u.user_id} value={u.user_id}>
                    {u.email}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="button"
              className="h-10 rounded-[10px] bg-primary px-5 text-sm font-medium text-white transition-colors hover:bg-primary/90 focus-visible:outline focus-visible:ring-2 focus-visible:ring-primary/35 disabled:opacity-50"
              disabled={!assignCustomerId || !assignUserId || assign.isPending}
              onClick={() => assign.mutate()}
            >
              Save assignment
            </button>
          </div>
        </div>
      ) : null}

      {orgId && assignments.isSuccess ? (
        <div className="overflow-x-auto rounded-2xl border border-border/60 bg-white shadow-card">
          <table className="min-w-full divide-y divide-border text-sm">
            <thead className="bg-surface-subtle/80 text-left text-xs font-semibold text-ink">
              <tr>
                <th className="px-4 py-3">Customer</th>
                <th className="px-4 py-3">Delivery manager</th>
                <th className="px-4 py-3">Valid from</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {assignments.data.items.length === 0 ? (
                <tr>
                  <td className="px-4 py-8 text-center text-ink-muted" colSpan={3}>
                    No assignments yet. Use the form above.
                  </td>
                </tr>
              ) : (
                assignments.data.items.map((row) => (
                  <tr key={row.assignment_id} className="hover:bg-neutral-50/80">
                    <td className="px-4 py-3 text-ink">{row.customer_legal}</td>
                    <td className="px-4 py-3 font-mono text-xs text-ink">{row.delivery_manager_email}</td>
                    <td className="px-4 py-3 font-mono text-xs text-ink-muted">{row.valid_from}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
