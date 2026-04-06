import { AlertCircle, FileSpreadsheet, Upload } from "lucide-react";
import { useCallback, useRef, useState } from "react";

interface ExcelDropZoneProps {
  disabled?: boolean;
  disabledReason?: string;
  onFile: (file: File) => void;
  error?: string | null;
}

export function ExcelDropZone({ disabled, disabledReason, onFile, error }: ExcelDropZoneProps) {
  const [drag, setDrag] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const pick = useCallback(
    (file: File) => {
      const ok =
        file.name.endsWith(".xlsx") ||
        file.name.endsWith(".xls") ||
        file.type === "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
      if (!ok) {
        return;
      }
      onFile(file);
    },
    [onFile],
  );

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        aria-disabled={disabled}
        aria-label="Excel upload drop zone"
        onKeyDown={(e) => {
          if (disabled) return;
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        onDragOver={(e) => {
          if (disabled) return;
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          if (disabled) return;
          e.preventDefault();
          setDrag(false);
          const f = e.dataTransfer.files[0];
          if (f) pick(f);
        }}
        className={`flex min-h-dropzone cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-4 py-10 transition-all ${
          disabled ? "cursor-not-allowed opacity-50" : ""
        } ${
          error
            ? "border-error bg-error-surface"
            : drag
              ? "border-primary scale-[1.01] bg-primary-muted shadow-glow"
              : "border-border/80 bg-gradient-to-b from-white to-slate-50/80 hover:border-primary/60 hover:shadow-md"
        }`}
        onClick={() => !disabled && inputRef.current?.click()}
      >
        {error ? (
          <AlertCircle className="mb-3 h-9 w-9 text-error" aria-hidden />
        ) : (
          <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/15 to-cyan-500/10 ring-1 ring-primary/20">
            <Upload className="h-7 w-7 text-primary" aria-hidden />
          </div>
        )}
        <p className="text-center text-sm font-semibold text-ink">
          {drag ? "Drop file to upload" : "Drag and drop your Excel file, or browse"}
        </p>
        <p className="mt-1 text-center text-xs text-ink-muted">.xlsx and .xls · max size per deployment</p>
        <button
          type="button"
          className="mt-5 rounded-xl bg-gradient-to-r from-primary to-teal-500 px-5 py-2.5 text-sm font-semibold text-white shadow-md shadow-teal-900/10 transition hover:brightness-105"
          onClick={(e) => {
            e.stopPropagation();
            inputRef.current?.click();
          }}
          disabled={disabled}
        >
          Browse files
        </button>
        <input
          ref={inputRef}
          type="file"
          accept=".xlsx,.xls,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) pick(f);
          }}
        />
        <FileSpreadsheet className="mt-2 h-5 w-5 text-slate-400" aria-hidden />
      </div>
      {error ? <p className="mt-2 text-sm text-error">{error}</p> : null}
      {disabled && disabledReason ? (
        <p className="mt-2 text-xs text-slate-500">{disabledReason}</p>
      ) : null}
    </div>
  );
}
