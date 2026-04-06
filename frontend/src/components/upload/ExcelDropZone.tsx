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
        className={`flex min-h-dropzone cursor-pointer flex-col items-center justify-center rounded-md border-2 border-dashed px-4 py-8 transition-colors ${
          disabled ? "cursor-not-allowed opacity-50" : ""
        } ${
          error
            ? "border-error bg-error-surface"
            : drag
              ? "border-accent bg-sky-50"
              : "border-border bg-surface-elevated hover:border-primary hover:bg-primary-muted"
        }`}
        onClick={() => !disabled && inputRef.current?.click()}
      >
        {error ? (
          <AlertCircle className="mb-2 h-8 w-8 text-error" aria-hidden />
        ) : (
          <Upload className="mb-2 h-8 w-8 text-slate-400" aria-hidden />
        )}
        <p className="text-center text-sm font-medium text-slate-800">
          {drag ? "Drop file to upload" : "Drag and drop your Excel file, or browse"}
        </p>
        <p className="mt-1 text-center text-xs text-slate-500">.xlsx and .xls · max size per deployment</p>
        <button
          type="button"
          className="mt-4 rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-hover"
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
