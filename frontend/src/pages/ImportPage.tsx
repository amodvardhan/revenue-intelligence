import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { ExcelDropZone } from "@/components/upload/ExcelDropZone";
import { FilePreviewTable } from "@/components/upload/FilePreviewTable";
import { ImportBatchHistory } from "@/components/upload/ImportBatchHistory";
import { ImportErrorList } from "@/components/upload/ImportErrorList";
import { ImportSuccessSummary } from "@/components/upload/ImportSuccessSummary";
import { IngestionProgressTracker } from "@/components/upload/IngestionProgressTracker";
import { api } from "@/services/api";
import { parseFirstSheetPreview } from "@/utils/parseExcelPreview";

const formSchema = z.object({
  org_id: z.string().uuid("Select organization"),
  period_start: z.string().optional(),
  period_end: z.string().optional(),
  replace: z.boolean(),
});

type FormValues = z.infer<typeof formSchema>;

interface OrgList {
  items: Array<{ org_id: string; org_name: string }>;
}

interface UploadSuccess {
  batch_id: string;
  status: string;
  total_rows?: number | null;
  loaded_rows?: number;
  period_start?: string | null;
  period_end?: string | null;
  error_log?: { errors?: Array<{ row?: number; column?: string; message: string }> };
  message?: string;
}

export function ImportPage() {
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<{
    headers: string[];
    rows: (string | number | null)[][];
    approx: number;
  } | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [terminal, setTerminal] = useState<
    | { kind: "success"; data: UploadSuccess & { filename: string } }
    | { kind: "failed"; data: UploadSuccess & { filename: string } }
    | { kind: "async"; batchId: string }
    | null
  >(null);

  const orgs = useQuery({
    queryKey: ["organizations"],
    queryFn: async () => {
      const { data } = await api.get<OrgList>("/api/v1/organizations");
      return data;
    },
  });

  const { register, handleSubmit, watch, setValue } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: { org_id: "" as FormValues["org_id"], replace: false },
    mode: "onSubmit",
  });

  const orgId = watch("org_id");

  const upload = useMutation({
    mutationFn: async (values: FormValues) => {
      if (!file) throw new Error("No file");
      const fd = new FormData();
      fd.append("file", file);
      fd.append("org_id", values.org_id);
      if (values.period_start) fd.append("period_start", values.period_start);
      if (values.period_end) fd.append("period_end", values.period_end);
      fd.append("replace", values.replace ? "true" : "false");
      const res = await api.post<UploadSuccess>("/api/v1/ingest/uploads", fd, {
        headers: { "Content-Type": "multipart/form-data" },
        validateStatus: (s) => s === 200 || s === 202 || s === 409,
      });
      return { status: res.status, data: res.data, filename: file.name };
    },
    onSuccess: (out) => {
      void qc.invalidateQueries({ queryKey: ["batches"] });
      if (out.status === 409) {
        setTerminal({
          kind: "failed",
          data: {
            batch_id: out.data.batch_id,
            status: "failed",
            filename: out.filename,
            error_log: { errors: [{ message: "Overlapping import — use replace or pick another period." }] },
          },
        });
        return;
      }
      if (out.status === 202 && out.data.batch_id) {
        setTerminal({ kind: "async", batchId: out.data.batch_id });
        return;
      }
      if (out.data.status === "completed") {
        setTerminal({ kind: "success", data: { ...out.data, filename: out.filename } });
        return;
      }
      setTerminal({ kind: "failed", data: { ...out.data, filename: out.filename } });
    },
  });

  const batches = useQuery({
    queryKey: ["batches"],
    queryFn: async () => {
      const { data } = await api.get<{
        items: Array<{
          batch_id: string;
          filename: string | null;
          status: string;
          total_rows: number | null;
          loaded_rows: number;
          started_at: string;
          completed_at: string | null;
        }>;
      }>("/api/v1/ingest/batches?limit=20");
      return data.items;
    },
  });

  const onPickFile = useCallback((f: File) => {
    setFile(f);
    setTerminal(null);
    setPreviewError(null);
    void f.arrayBuffer().then((buf) => {
      try {
        const p = parseFirstSheetPreview(buf);
        setPreview({ headers: p.headers, rows: p.rows, approx: p.rowCountApprox });
      } catch (e) {
        setPreview(null);
        setPreviewError(e instanceof Error ? e.message : "Parse error");
      }
    });
  }, []);

  const firstOrg = orgs.data?.items[0]?.org_id;

  useEffect(() => {
    if (firstOrg) {
      setValue("org_id", firstOrg, { shouldValidate: true });
    }
  }, [firstOrg, setValue]);

  return (
    <div className="mx-auto max-w-4xl space-y-8 px-6 py-10">
      <header className="border-b border-black/[0.06] pb-8">
        <h1 className="page-headline">Import</h1>
        <p className="page-lede">
          Use the <strong className="font-medium text-ink">EUROPE Weekly Commercial</strong> workbook (Sheet1, row 2
          headers: Sr. No., Customer names, monthly columns) or a classic file with{" "}
          <span className="font-mono text-[13px]">amount</span>,{" "}
          <span className="font-mono text-[13px]">revenue_date</span>
          ; optional business_unit, division, customer, revenue_type.
        </p>
      </header>

      <form
        className="space-y-6"
        onSubmit={handleSubmit((v) => {
          setTerminal(null);
          upload.mutate(v);
        })}
      >
        <div className="surface-card grid gap-4 p-5 sm:grid-cols-2">
          <div>
            <label className="small-caps-label mb-1.5 block">Organization</label>
            <select
              className="input-modern !h-10 w-full"
              {...register("org_id", { required: true })}
              defaultValue={firstOrg}
            >
              <option value="">Select organization</option>
              {orgs.data?.items.map((o) => (
                <option key={o.org_id} value={o.org_id}>
                  {o.org_name}
                </option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="small-caps-label mb-1.5 block">Period start</label>
              <input type="date" className="input-modern !h-10 w-full" {...register("period_start")} />
            </div>
            <div>
              <label className="small-caps-label mb-1.5 block">Period end</label>
              <input type="date" className="input-modern !h-10 w-full" {...register("period_end")} />
            </div>
          </div>
        </div>
        <label className="flex items-center gap-3 rounded-[10px] border border-black/[0.08] bg-amber-50/80 px-4 py-3 text-[13px] leading-snug text-neutral-900">
          <input
            type="checkbox"
            {...register("replace", {
              setValueAs: (v) => v === true || v === "on",
            })}
          />
          Replace overlapping scope (deletes existing facts in period for this org)
        </label>

        <ExcelDropZone
          disabled={!orgId}
          disabledReason={!orgId ? "Select an organization first" : undefined}
          onFile={onPickFile}
          error={null}
        />

        {file && preview ? (
          <FilePreviewTable
            headers={preview.headers}
            rows={preview.rows}
            fileName={file.name}
            approxRows={preview.approx}
            error={previewError}
          />
        ) : null}

        {upload.isPending ? (
          <IngestionProgressTracker step="validate" asyncMode={false} />
        ) : null}

        {terminal?.kind === "async" ? (
          <IngestionProgressTracker step="commit" asyncMode batchId={terminal.batchId} />
        ) : null}

        {terminal?.kind === "success" ? (
          <ImportSuccessSummary
            batchId={terminal.data.batch_id}
            filename={terminal.data.filename}
            loadedRows={terminal.data.loaded_rows ?? 0}
            totalRows={terminal.data.total_rows ?? null}
            periodStart={terminal.data.period_start ?? null}
            periodEnd={terminal.data.period_end ?? null}
            completedAt={new Date().toISOString()}
          />
        ) : null}

        {terminal?.kind === "failed" && terminal.data.error_log?.errors ? (
          <ImportErrorList errors={terminal.data.error_log.errors} />
        ) : null}

        <button
          type="submit"
          disabled={!file || !orgId || upload.isPending}
          className="btn-primary-solid px-8 disabled:cursor-not-allowed"
        >
          {upload.isPending ? "Importing…" : "Start import"}
        </button>
      </form>

      <ImportBatchHistory
        items={
          batches.data?.map((b) => ({
            batch_id: b.batch_id,
            filename: b.filename,
            status: b.status,
            total_rows: b.total_rows,
            loaded_rows: b.loaded_rows,
            started_at: b.started_at,
            completed_at: b.completed_at,
          })) ?? []
        }
        loading={batches.isLoading}
        error={batches.error ? "Could not load history" : null}
        onRetry={() => void batches.refetch()}
      />
    </div>
  );
}
