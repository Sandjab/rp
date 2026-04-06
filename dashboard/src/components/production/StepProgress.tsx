import { PHASE_LABELS, type PhaseName } from "@/lib/types";

interface StepProgressProps {
  phase: PhaseName;
  elapsed?: number;
}

function formatElapsed(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (m === 0) return `${s}s`;
  return `${m}m${s.toString().padStart(2, "0")}s`;
}

export function StepProgress({ phase, elapsed }: StepProgressProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-16">
      {/* CSS spinner */}
      <div
        className="h-10 w-10 animate-spin rounded-full border-4 border-muted border-t-primary"
        role="status"
      />

      <div className="flex flex-col items-center gap-1">
        <span className="text-sm font-medium text-foreground">
          {PHASE_LABELS[phase]}
        </span>
        <span className="text-xs text-muted-foreground">En cours...</span>
        {elapsed != null && (
          <span className="text-xs tabular-nums text-muted-foreground">
            {formatElapsed(elapsed)}
          </span>
        )}
      </div>
    </div>
  );
}
