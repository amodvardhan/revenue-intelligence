import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { api } from "@/services/api";

interface OrgList {
  items: Array<{ org_id: string; org_name: string }>;
}

interface CustomerRef {
  customer_id: string;
  customer_name: string;
}

interface ProjectRow {
  project_id: string;
  org_id: string;
  customer_id: string | null;
  project_name: string;
  project_code: string | null;
  is_active: boolean;
}

export function ProjectsPage() {
  const queryClient = useQueryClient();
  const [orgId, setOrgId] = useState("");
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [customerId, setCustomerId] = useState("");
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

  const projects = useQuery({
    queryKey: ["projects", orgId],
    queryFn: async () => {
      const { data } = await api.get<{ items: ProjectRow[] }>("/api/v1/projects", {
        params: { org_id: orgId },
      });
      return data;
    },
    enabled: Boolean(orgId),
    retry: false,
  });

  const createProject = useMutation({
    mutationFn: async () => {
      const { data } = await api.post<ProjectRow>("/api/v1/projects", {
        org_id: orgId,
        project_name: name.trim(),
        project_code: code.trim() || null,
        customer_id: customerId || null,
      });
      return data;
    },
    onSuccess: () => {
      setBanner(null);
      setName("");
      setCode("");
      setCustomerId("");
      void queryClient.invalidateQueries({ queryKey: ["projects", orgId] });
    },
    onError: () => {
      setBanner("Could not create project. Check permissions (Admin, IT Admin, Finance, or BU head on this org).");
    },
  });

  const customerLabel = useMemo(() => {
    const map = new Map<string, string>();
    for (const c of customers.data?.items ?? []) {
      map.set(c.customer_id, c.customer_name);
    }
    return (id: string | null) => (id ? map.get(id) ?? id : "—");
  }, [customers.data?.items]);

  return (
    <div className="mx-auto max-w-5xl space-y-8 px-6 py-10">
      <header className="border-b border-black/[0.06] pb-8">
        <h1 className="page-headline">Projects</h1>
        <p className="page-lede">
          Create and track delivery or commercial projects under an organization. Optionally link a customer (create
          customers on the Customers page first if the list is empty). Revenue facts do not need to reference a project
          yet; projects are for operational visibility and future linkage.
        </p>
      </header>

      {projects.isError ? (
        <div className="rounded-xl border border-neutral-200 bg-neutral-50 px-4 py-3 text-sm text-neutral-800" role="status">
          Projects could not be loaded. Ensure you have access to the organization.
        </div>
      ) : null}

      {orgId ? (
        <div className="surface-card space-y-4 p-6">
          <h2 className="text-sm font-semibold text-ink">New project</h2>
          {banner ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50/90 px-3 py-2 text-sm text-amber-950">{banner}</div>
          ) : null}
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <label className="small-caps-label mb-1.5 block">Organization</label>
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
              <label className="small-caps-label mb-1.5 block">Project name</label>
              <input
                className="input-modern !h-10 w-full"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. EMEA rollout — Globex"
              />
            </div>
            <div>
              <label className="small-caps-label mb-1.5 block">Code (optional)</label>
              <input
                className="input-modern !h-10 w-full"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="Internal code"
              />
            </div>
            <div>
              <label className="small-caps-label mb-1.5 block">Customer (optional)</label>
              <select
                className="input-modern !h-10 w-full"
                value={customerId}
                onChange={(e) => setCustomerId(e.target.value)}
                disabled={customers.isLoading}
              >
                <option value="">None</option>
                {customers.data?.items.map((c) => (
                  <option key={c.customer_id} value={c.customer_id}>
                    {c.customer_name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <button
            type="button"
            className="h-10 rounded-[10px] bg-primary px-5 text-sm font-medium text-white transition-colors hover:bg-primary/90 focus-visible:outline focus-visible:ring-2 focus-visible:ring-primary/35 disabled:opacity-50"
            disabled={!name.trim() || createProject.isPending}
            onClick={() => {
              setBanner(null);
              createProject.mutate();
            }}
          >
            Create project
          </button>
        </div>
      ) : null}

      {projects.isSuccess ? (
        <div className="overflow-x-auto rounded-2xl border border-border/60 bg-white shadow-card">
          <table className="min-w-full divide-y divide-border text-sm">
            <thead className="bg-surface-subtle/80 text-left text-xs font-semibold text-ink">
              <tr>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Code</th>
                <th className="px-4 py-3">Customer</th>
                <th className="px-4 py-3">Active</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {projects.data.items.length === 0 ? (
                <tr>
                  <td className="px-4 py-8 text-center text-ink-muted" colSpan={4}>
                    No projects yet for this organization.
                  </td>
                </tr>
              ) : (
                projects.data.items.map((p) => (
                  <tr key={p.project_id} className="hover:bg-neutral-50/80">
                    <td className="px-4 py-3 text-ink">{p.project_name}</td>
                    <td className="px-4 py-3 font-mono text-xs text-ink-muted">{p.project_code ?? "—"}</td>
                    <td className="px-4 py-3 text-sm text-ink">{customerLabel(p.customer_id)}</td>
                    <td className="px-4 py-3 text-ink-muted">{p.is_active ? "Yes" : "No"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      ) : null}

      {projects.isLoading ? <p className="text-sm text-ink-muted">Loading projects…</p> : null}
    </div>
  );
}
