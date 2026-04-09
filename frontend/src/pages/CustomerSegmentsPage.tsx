import { useQuery } from "@tanstack/react-query";

import { api } from "@/services/api";

const phase5 = import.meta.env.VITE_ENABLE_PHASE5 === "true";

export function CustomerSegmentsPage() {
  const defs = useQuery({
    queryKey: ["segment-definitions"],
    queryFn: async () => {
      const { data } = await api.get<{ items: Array<{ segment_id: string; name: string; version: number }> }>(
        "/api/v1/segments/definitions",
      );
      return data;
    },
    enabled: phase5,
  });

  if (!phase5) {
    return (
      <div className="page-shell page-shell--md page-shell--tight">
        <h1 className="page-headline">Customer segments</h1>
        <p className="mt-2 text-sm text-ink-muted">Set VITE_ENABLE_PHASE5=true and ENABLE_PHASE5=true on the API to use this screen.</p>
      </div>
    );
  }

  return (
    <div className="page-shell page-shell--md">
      <header className="page-header-block">
        <h1 className="page-headline">Customer segments</h1>
        <p className="page-lede max-w-2xl">Segment rules are stored and replayable; materialize membership from the API.</p>
      </header>

      {defs.isLoading ? <p className="text-sm text-ink-muted">Loading…</p> : null}
      {defs.isError ? <p className="text-sm text-error">Could not load definitions.</p> : null}
      <ul className="space-y-2">
        {(defs.data?.items ?? []).map((s) => (
          <li key={s.segment_id} className="surface-card px-4 py-3 text-sm text-ink">
            {s.name} <span className="text-xs text-ink-muted">v{s.version}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
