import { cn } from "@/lib/utils";
import {
  PHASE_ORDER,
  PHASE_LABELS,
  type PhaseName,
  type PhaseStatus,
} from "@/lib/types";

interface StepperProps {
  phaseStatus: Record<PhaseName, PhaseStatus>;
  phaseTimes: Record<string, { start?: number; end?: number; duration?: number }>;
  editionNumber?: number;
  editionDate?: string;
}

function statusIcon(status: PhaseStatus, index: number) {
  switch (status) {
    case "done":
      return "\u2713";
    case "running":
    case "resumed":
      return "\u25CF";
    case "error":
      return "\u2717";
    case "skipped":
      return "\u2014";
    case "paused":
      return "\u23F8";
    default:
      return String(index + 1);
  }
}

function statusColor(status: PhaseStatus) {
  switch (status) {
    case "done":
      return "text-emerald-400 border-emerald-400";
    case "running":
    case "resumed":
      return "text-red-400 border-red-400 animate-pulse";
    case "paused":
      return "text-amber-400 border-amber-400";
    case "error":
      return "text-destructive border-destructive";
    case "skipped":
      return "text-muted-foreground border-muted-foreground";
    default:
      return "text-muted-foreground/50 border-muted-foreground/50";
  }
}

function formatDuration(seconds: number) {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m${s.toString().padStart(2, "0")}s`;
}

export function Stepper({
  phaseStatus,
  phaseTimes,
  editionNumber,
  editionDate,
}: StepperProps) {
  return (
    <div className="flex w-[160px] shrink-0 flex-col gap-1 py-2">
      {PHASE_ORDER.map((phase, i) => {
        const status = phaseStatus[phase] ?? "pending";
        const times = phaseTimes[phase];
        const duration = times?.duration;

        return (
          <div key={phase} className="flex items-center gap-2 px-2 py-1.5">
            <span
              className={cn(
                "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs font-medium",
                statusColor(status),
              )}
            >
              {statusIcon(status, i)}
            </span>
            <div className="flex flex-col leading-tight">
              <span className="text-xs font-medium text-foreground">
                {PHASE_LABELS[phase]}
              </span>
              {duration != null && (
                <span className="text-[10px] text-muted-foreground">
                  {formatDuration(duration)}
                </span>
              )}
            </div>
          </div>
        );
      })}

      {editionNumber != null && (
        <div className="mt-auto border-t border-border px-2 pt-3 text-[10px] text-muted-foreground">
          Edition #{editionNumber}
          {editionDate && <> &middot; {editionDate}</>}
        </div>
      )}
    </div>
  );
}
