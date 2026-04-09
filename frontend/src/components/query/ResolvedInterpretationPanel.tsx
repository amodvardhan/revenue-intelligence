interface ResolvedInterpretationPanelProps {
  interpretation: string;
}

export function ResolvedInterpretationPanel({ interpretation }: ResolvedInterpretationPanelProps) {
  return (
    <div className="mt-4 rounded-md border border-border bg-surface-elevated p-4 shadow-sm">
      <h2 className="text-heading">Interpretation</h2>
      <p className="mt-2 text-[15px] leading-relaxed text-ink">{interpretation}</p>
    </div>
  );
}
