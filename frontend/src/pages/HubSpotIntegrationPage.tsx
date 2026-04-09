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
    <div className="page-shell page-shell--lg">
      <header className="page-header-block">
        <h1 className="page-headline">HubSpot integration</h1>
        <p className="page-lede max-w-3xl">
          Connect HubSpot for CRM-sourced pipeline and deal data. Booked revenue actuals from Excel remain
          authoritative where the product policy applies; conflicts surface in reconciliation, not as silent
          overwrites.
        </p>
      </header>

      {oauthMsg ? (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
          {oauthMsg}
        </div>
      ) : null}

      <section className="surface-card p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="rounded-xl bg-primary-muted p-2.5 ring-1 ring-primary/10">
              <Plug className="h-5 w-5 text-primary" aria-hidden />
            </div>
            <div>
              <h2 className="text-heading">Connection</h2>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                {statusQ.isLoading ? (
                  <span className="inline-flex items-center gap-1 text-sm text-ink-muted">
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
                  <span className="inline-flex items-center gap-1 rounded-full bg-neutral-100 px-2 py-0.5 text-micro text-ink-muted">
                    <Link2 className="h-3.5 w-3.5" aria-hidden />
                    Disconnected
                  </span>
                )}
              </div>
              {st?.hubspot_portal_id ? (
                <p className="mt-2 font-mono text-xs text-ink-muted">Portal ID: {st.hubspot_portal_id}</p>
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
              className="btn-primary-solid gap-2 px-4 py-2 text-sm disabled:cursor-not-allowed"
            >
              {connectMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              {connected ? "Connected" : "Connect to HubSpot"}
            </button>
            <button
              type="button"
              onClick={() => disconnectMut.mutate()}
              disabled={!connected || disconnectMut.isPending}
              className="btn-secondary-solid px-4 py-2 text-sm disabled:cursor-not-allowed"
            >
              Disconnect
            </button>
          </div>
        </div>
      </section>

      <section className="surface-card p-6">
        <h2 className="text-heading">Sync</h2>
        <p className="mt-1 text-sm text-ink-muted">
          Manual sync runs in the background. Use sync history for governance and correlation IDs.
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => syncMut.mutate()}
            disabled={!connected || syncMut.isPending}
            className="btn-primary-solid gap-2 px-4 py-2 text-sm disabled:cursor-not-allowed"
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
        <h2 className="text-heading">Sync history</h2>
        <div className="table-modern-wrap mt-3">
          <table className="table-modern text-left">
            <thead>
              <tr className="border-b border-black/[0.06] bg-neutral-50/90 text-left text-[13px] font-semibold text-ink-muted">
                <th className="px-4 py-2.5">Started</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5">Rows</th>
                <th className="px-4 py-2.5">Correlation</th>
              </tr>
            </thead>
            <tbody>
              {runsQ.isLoading ? (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-ink-muted">
                    <Loader2 className="mx-auto h-5 w-5 animate-spin" />
                  </td>
                </tr>
              ) : runsQ.data?.length ? (
                runsQ.data.map((r) => (
                  <tr key={r.sync_run_id} className="border-b border-neutral-100 last:border-0">
                    <td className="px-4 py-2.5 font-mono text-sm tabular-nums text-ink">{r.started_at}</td>
                    <td className="px-4 py-2.5">{r.status}</td>
                    <td className="px-4 py-2.5 font-mono text-sm tabular-nums text-ink-muted">
                      {r.rows_loaded} loaded / {r.rows_failed} failed / {r.rows_fetched} fetched
                    </td>
                    <td className="px-4 py-2.5 font-mono text-xs text-ink-muted">
                      {r.correlation_id ?? "—"}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-ink-muted">
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
