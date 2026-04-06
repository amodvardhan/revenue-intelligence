import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, AlertTriangle, CheckCircle2, Link2, Loader2, Plug, RefreshCw } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import { api } from "@/services/api";

type HubspotStatus = {
  status: string;
  hubspot_portal_id: string | null;
  token_expires_at: string | null;
  last_token_refresh_at: string | null;
  last_error: string | null;
  scopes_granted: string | null;
};

type SyncRun = {
  sync_run_id: string;
  trigger: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  rows_fetched: number;
  rows_loaded: number;
  rows_failed: number;
  error_summary: string | null;
  correlation_id: string | null;
};

export function HubSpotIntegrationPage() {
  const qc = useQueryClient();
  const [params] = useSearchParams();
  const oauthMsg = params.get("connected") ? "Connection updated — refresh status below." : null;

  const statusQ = useQuery({
    queryKey: ["hubspot", "status"],
    queryFn: async () => {
      const { data } = await api.get<HubspotStatus>("/api/v1/integrations/hubspot/status");
      return data;
    },
  });

  const runsQ = useQuery({
    queryKey: ["hubspot", "sync-runs"],
    queryFn: async () => {
      const { data } = await api.get<{ items: SyncRun[] }>("/api/v1/integrations/hubspot/sync-runs");
      return data.items;
    },
  });

  const connectMut = useMutation({
    mutationFn: async () => {
      const { data } = await api.get<{ authorization_url: string; state: string }>(
        "/api/v1/integrations/hubspot/oauth/authorize-url",
      );
      window.location.href = data.authorization_url;
    },
  });

  const disconnectMut = useMutation({
    mutationFn: async () => {
      await api.post("/api/v1/integrations/hubspot/disconnect", {});
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["hubspot"] });
    },
  });

  const syncMut = useMutation({
    mutationFn: async () => {
      const { data } = await api.post<{ sync_run_id: string }>("/api/v1/integrations/hubspot/sync", {
        mode: "incremental",
      });
      return data;
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["hubspot"] });
    },
  });

  const st = statusQ.data;
  const connected = st?.status === "connected";
  const unhealthy = st?.status === "error" || st?.status === "token_refresh_failed";

  return (
    <div className="space-y-8 p-8">
      <div>
        <h1 className="text-display text-slate-900">HubSpot integration</h1>
        <p className="mt-2 max-w-3xl text-sm text-slate-600">
          Connect HubSpot for CRM-sourced pipeline and deal data. Booked revenue actuals from Excel remain
          authoritative where the product policy applies; conflicts surface in reconciliation, not as silent
          overwrites.
        </p>
      </div>

      {oauthMsg ? (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
          {oauthMsg}
        </div>
      ) : null}

      <section className="rounded-lg border border-border bg-surface-elevated p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="rounded-md bg-primary-muted p-2">
              <Plug className="h-5 w-5 text-primary" aria-hidden />
            </div>
            <div>
              <h2 className="text-heading font-semibold text-slate-900">Connection</h2>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                {statusQ.isLoading ? (
                  <span className="inline-flex items-center gap-1 text-sm text-slate-600">
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                    Loading status…
                  </span>
                ) : statusQ.isError ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-error-surface px-2 py-0.5 text-micro text-error">
                    <AlertCircle className="h-3.5 w-3.5" aria-hidden />
                    Could not load status
                  </span>
                ) : connected ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-success-muted px-2 py-0.5 text-micro text-emerald-900">
                    <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
                    Connected
                  </span>
                ) : unhealthy ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-warning-surface px-2 py-0.5 text-micro text-amber-900">
                    <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
                    {st?.status === "token_refresh_failed" ? "Token refresh failed" : "Error"}
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-micro text-slate-700">
                    <Link2 className="h-3.5 w-3.5" aria-hidden />
                    Disconnected
                  </span>
                )}
              </div>
              {st?.hubspot_portal_id ? (
                <p className="mt-2 text-xs text-slate-500">Portal ID: {st.hubspot_portal_id}</p>
              ) : null}
              {st?.last_error ? (
                <p className="mt-2 text-sm text-amber-800">{st.last_error}</p>
              ) : null}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => connectMut.mutate()}
              disabled={connectMut.isPending || connected}
              className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {connectMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              {connected ? "Connected" : "Connect to HubSpot"}
            </button>
            <button
              type="button"
              onClick={() => disconnectMut.mutate()}
              disabled={!connected || disconnectMut.isPending}
              className="rounded-md border border-border bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Disconnect
            </button>
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-border bg-surface-elevated p-6 shadow-sm">
        <h2 className="text-heading font-semibold text-slate-900">Sync</h2>
        <p className="mt-1 text-sm text-slate-600">
          Manual sync runs in the background. Use sync history for governance and correlation IDs.
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => syncMut.mutate()}
            disabled={!connected || syncMut.isPending}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {syncMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Sync now
          </button>
          {syncMut.isError ? (
            <span className="text-sm text-red-700">Sync could not be started (check role or HubSpot settings).</span>
          ) : null}
        </div>
      </section>

      <section>
        <h2 className="text-heading font-semibold text-slate-900">Sync history</h2>
        <div className="mt-3 overflow-x-auto rounded-lg border border-border bg-white">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-border bg-slate-50 text-xs uppercase text-slate-600">
              <tr>
                <th className="px-4 py-2">Started</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Rows</th>
                <th className="px-4 py-2">Correlation</th>
              </tr>
            </thead>
            <tbody>
              {runsQ.isLoading ? (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-slate-500">
                    <Loader2 className="mx-auto h-5 w-5 animate-spin" />
                  </td>
                </tr>
              ) : runsQ.data?.length ? (
                runsQ.data.map((r) => (
                  <tr key={r.sync_run_id} className="border-b border-border last:border-0">
                    <td className="px-4 py-2 tabular-nums text-slate-800">{r.started_at}</td>
                    <td className="px-4 py-2">{r.status}</td>
                    <td className="px-4 py-2 tabular-nums text-slate-700">
                      {r.rows_loaded} loaded / {r.rows_failed} failed / {r.rows_fetched} fetched
                    </td>
                    <td className="px-4 py-2 font-mono text-xs text-slate-600">
                      {r.correlation_id ?? "—"}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-slate-500">
                    No sync runs yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
