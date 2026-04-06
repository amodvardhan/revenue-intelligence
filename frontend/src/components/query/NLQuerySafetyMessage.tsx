import { AlertCircle } from "lucide-react";

interface NLQuerySafetyMessageProps {
  title: string;
  message: string;
  variant?: "error" | "warning";
}

export function NLQuerySafetyMessage({ title, message, variant = "error" }: NLQuerySafetyMessageProps) {
  const box =
    variant === "error"
      ? "border-red-200 bg-red-50 text-red-900"
      : "border-amber-200 bg-amber-50 text-amber-900";

  return (
    <div className={`mt-4 flex gap-3 rounded-md border p-4 ${box}`} role="alert">
      <AlertCircle className="h-5 w-5 shrink-0" aria-hidden />
      <div>
        <p className="text-body-strong font-medium">{title}</p>
        <p className="text-body mt-1 text-sm opacity-90">{message}</p>
      </div>
    </div>
  );
}
