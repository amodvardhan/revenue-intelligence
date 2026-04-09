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
        className={`flex min-h-dropzone cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-4 py-10 transition-colors ${
          disabled ? "cursor-not-allowed opacity-50" : ""
        } ${
          error
            ? "border-error bg-error-surface"
            : drag
              ? "border-primary bg-primary-muted"
              : "border-black/[0.12] bg-white hover:border-primary/50"
        }`}
        onClick={() => !disabled && inputRef.current?.click()}
      >
        {error ? (
          <AlertCircle className="mb-3 h-9 w-9 text-error" aria-hidden />
        ) : (
          <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-neutral-100">
            <Upload className="h-7 w-7 text-neutral-600" aria-hidden />
          </div>
        )}
        <p className="text-center text-sm font-semibold text-ink">
          {drag ? "Drop file to upload" : "Drag and drop your Excel file, or browse"}
        </p>
        <p className="mt-1 text-center text-xs text-ink-muted">.xlsx and .xls · max size per deployment</p>
        <button
          type="button"
          className="btn-primary-solid mt-5 px-5"
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
        <FileSpreadsheet className="mt-2 h-5 w-5 text-neutral-400" aria-hidden />
      </div>
      {error ? <p className="mt-2 text-sm text-error">{error}</p> : null}
      {disabled && disabledReason ? (
        <p className="mt-2 text-xs text-ink-muted">{disabledReason}</p>
      ) : null}
    </div>
  );
}
