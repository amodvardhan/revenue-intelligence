import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api } from "@/services/api";

interface OrgList {
  items: Array<{ org_id: string; org_name: string }>;
}

interface OrgRole {
  org_id: string;
  org_name: string;
  role: string;
}

interface TenantUser {
  user_id: string;
  email: string;
  is_active: boolean;
  /** Present on API responses; may be absent on stale cache / partial payloads. */
  org_roles?: OrgRole[];
}

const ROLE_OPTIONS = [
  { value: "viewer", label: "Viewer" },
  { value: "cxo", label: "CXO" },
  { value: "bu_head", label: "BU head" },
  { value: "finance", label: "Finance" },
  { value: "admin", label: "Admin" },
  { value: "it_admin", label: "IT admin" },
] as const;

export function TeamUsersPage() {
  const queryClient = useQueryClient();
  const [orgId, setOrgId] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<string>("viewer");
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

  const users = useQuery({
    queryKey: ["tenant-users"],
    queryFn: async () => {
      const { data } = await api.get<{ items: TenantUser[] }>("/api/v1/tenant/users");
      return data;
    },
    retry: false,
  });

  const createUser = useMutation({
    mutationFn: async () => {
      const { data } = await api.post<{ user_id: string; email: string }>("/api/v1/tenant/users", {
        email: email.trim(),
        password,
        org_id: orgId,
        role,
      });
      return data;
    },
    onSuccess: () => {
      setBanner(null);
      setEmail("");
      setPassword("");
      void queryClient.invalidateQueries({ queryKey: ["tenant-users"] });
    },
    onError: () => {
      setBanner("Could not create user. You need Admin or IT Admin on the organization, or the email may already exist.");
    },
  });

  const loadError =
    users.isError && users.error && typeof users.error === "object" && "response" in users.error
      ? (users.error as { response?: { status?: number } }).response?.status === 403
      : false;

  return (
    <div className="page-shell page-shell--md">
      <header className="page-header-block">
        <h1 className="page-headline">Team users</h1>
        <p className="page-lede">
          Create directory accounts in your tenant so they can sign in and be chosen as delivery managers or assigned
          roles. Only Admin or IT Admin on an organization can add users to that organization.
        </p>
      </header>

      {loadError ? (
        <div className="rounded-xl border border-neutral-200 bg-neutral-50 px-4 py-3 text-sm text-neutral-800" role="status">
          You do not have access to list or create users. Ask an organization admin or IT admin.
        </div>
      ) : null}

      {users.isSuccess ? (
        <div className="surface-card space-y-4 p-6">
          <h2 className="text-heading text-[15px]">Add user</h2>
          {banner ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50/90 px-3 py-2 text-sm text-amber-950">{banner}</div>
          ) : null}
          <div className="flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-end">
            <div className="min-w-[200px] flex-1">
              <label className="form-field-label">Organization (first role)</label>
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
            <div className="min-w-[220px] flex-1">
              <label className="form-field-label">Email</label>
              <input
                type="email"
                autoComplete="off"
                className="input-modern !h-10 w-full"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@company.com"
              />
            </div>
            <div className="min-w-[180px] flex-1">
              <label className="form-field-label">Temporary password</label>
              <input
                type="password"
                autoComplete="new-password"
                className="input-modern !h-10 w-full"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Min. 8 characters"
              />
            </div>
            <div className="min-w-[160px]">
              <label className="form-field-label">Role</label>
              <select className="input-modern !h-10 w-full" value={role} onChange={(e) => setRole(e.target.value)}>
                {ROLE_OPTIONS.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="button"
              className="h-10 rounded-[10px] bg-primary px-5 text-sm font-medium text-white transition-colors hover:bg-primary/90 focus-visible:outline focus-visible:ring-2 focus-visible:ring-primary/35 disabled:opacity-50"
              disabled={!orgId || !email || password.length < 8 || createUser.isPending}
              onClick={() => {
                setBanner(null);
                createUser.mutate();
              }}
            >
              Create user
            </button>
          </div>
        </div>
      ) : null}

      {users.isSuccess && users.data ? (
        <div className="overflow-x-auto rounded-2xl border border-border/60 bg-white shadow-card">
          <table className="min-w-full divide-y divide-border text-sm">
            <thead className="bg-surface-subtle/80 text-left text-xs font-semibold text-ink">
              <tr>
                <th className="px-4 py-3">Email</th>
                <th className="px-4 py-3">Active</th>
                <th className="px-4 py-3">Organization roles</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {(users.data.items ?? []).map((u) => {
                const orgRoles = u.org_roles ?? [];
                return (
                  <tr key={u.user_id} className="hover:bg-neutral-50/80">
                    <td className="px-4 py-3 font-mono text-xs text-ink">{u.email}</td>
                    <td className="px-4 py-3 text-ink-muted">{u.is_active ? "Yes" : "No"}</td>
                    <td className="px-4 py-3 text-xs text-ink">
                      {orgRoles.length === 0 ? (
                        <span className="text-ink-muted">—</span>
                      ) : (
                        <ul className="list-inside list-disc space-y-0.5">
                          {orgRoles.map((r) => (
                            <li key={`${r.org_id}-${r.role}`}>
                              {r.org_name}: {r.role}
                            </li>
                          ))}
                        </ul>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}

      {users.isLoading ? <p className="text-sm text-ink-muted">Loading…</p> : null}
    </div>
  );
}
