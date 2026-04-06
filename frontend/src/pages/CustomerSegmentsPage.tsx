import { useQuery } from "@tanstack/react-query";

import { api } from "@/services/api";

const phase5 = import.meta.env.VITE_ENABLE_PHASE5 === "true";

export function CustomerSegmentsPage() {
  const defs = useQuery({
    queryKey: ["segment-definitions"],
    queryFn: async () => {
      const { data } = await api.get<{ items: Array<{ segment_id: string; name: string; version: number }> }>(
        "/api/v1/segments/definitions"
      );
      return data;
    },
    enabled: phase5,
  });

  if (!phase5) {
    return (
      <div className="p-8">
        <h1 className="text-display text-slate-900">Customer segments</h1>
        <p className="mt-2 text-sm text-slate-600">Set VITE_ENABLE_PHASE5=true and ENABLE_PHASE5=true on the API.</p>
      </div>
    );
  }

  return (
    <div className="p-8">
      <h1 className="text-display text-slate-900">Customer segments</h1>
      <p className="mt-1 text-sm text-slate-600">Segment rules are stored and replayable; materialize membership from the API.</p>
      {defs.isLoading ? <p className="mt-4 text-sm">Loading…</p> : null}
      {defs.isError ? <p className="mt-4 text-sm text-red-600">Could not load definitions.</p> : null}
      <ul className="mt-4 space-y-2">
        {(defs.data?.items ?? []).map((s) => (
          <li key={s.segment_id} className="rounded border border-border bg-white px-3 py-2 text-sm">
            {s.name}{" "}
            <span className="text-xs text-slate-500">v{s.version}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
