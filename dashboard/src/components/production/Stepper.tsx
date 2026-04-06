import { cn } from "@/lib/utils";
import {
  PHASE_ORDER,
  PHASE_LABELS,
  type PhaseName,
  type PhaseStatus,
  type ArtifactInfo,
  type PhaseAvailability,
} from "@/lib/types";

interface StepperProps {
  phaseStatus: Record<PhaseName, PhaseStatus>;
  phaseTimes: Record<string, { start?: number; end?: number; duration?: number }>;
  editionNumber?: number;
  editionDate?: string;
  mode: "running" | "idle";
  artifacts?: Record<string, ArtifactInfo>;
  onStepClick?: (phase: PhaseName) => void;
}

// ── Dependency logic ────────────────────────────────────────────────────────

function getPhaseAvailability(
  phase: PhaseName,
  artifacts: Record<string, ArtifactInfo>,
): PhaseAvailability {
  const has = (key: string) => artifacts[key]?.exists === true;

  switch (phase) {
    case "websearch":
      return has("websearch") ? "done" : "available";
    case "collect":
      return has("collect") ? "done" : "available";
    case "editorial":
      if (has("editorial")) return "done";
      return has("collect") ? "available" : "blocked";
    case "editor":
      if (has("editor")) return "done";
      return has("editorial") ? "available" : "blocked";
    case "image":
      if (has("image")) return "done";
      return has("editor") ? "available" : "blocked";
    case "html":
      if (has("html")) return "done";
      return has("editor") ? "available" : "blocked";
    case "deploy":
      return has("html") ? "available" : "blocked";
  }
}

// ── Running-mode helpers ────────────────────────────────────────────────────

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

// ── Idle-mode helpers ───────────────────────────────────────────────────────

function idleIcon(availability: PhaseAvailability) {
  switch (availability) {
    case "done":
      return "\u2713";
    case "available":
      return "\u25B6";
    case "blocked":
      return "\uD83D\uDD12";
  }
}

function idleColor(availability: PhaseAvailability) {
  switch (availability) {
    case "done":
      return "text-emerald-400/60 border-emerald-400/60";
    case "available":
      return "text-blue-400 border-blue-400";
    case "blocked":
      return "text-muted-foreground/40 border-muted-foreground/40";
  }
}

function formatRelativeTime(isoString: string): string {
  const now = Date.now();
  const then = new Date(isoString).getTime();
  const diffMs = now - then;

  if (diffMs < 0) return "a l'instant";

  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 1) return "a l'instant";
  if (minutes < 60) return `il y a ${minutes}min`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `il y a ${hours}h`;

  const days = Math.floor(hours / 24);
  return `il y a ${days}j`;
}

// ── Component ───────────────────────────────────────────────────────────────

export function Stepper({
  phaseStatus,
  phaseTimes,
  editionNumber,
  editionDate,
  mode,
  artifacts,
  onStepClick,
}: StepperProps) {
  return (
    <div className="flex w-[160px] shrink-0 flex-col gap-1 py-2">
      {PHASE_ORDER.map((phase, i) => {
        if (mode === "running") {
          // ── Running mode: original behavior ──
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
        }

        // ── Idle mode: artifact-based, clickable ──
        const art = artifacts?.[phase];
        const availability = artifacts
          ? getPhaseAvailability(phase, artifacts)
          : "blocked";
        const isClickable = availability === "available" || availability === "done";

        return (
          <div
            key={phase}
            className={cn(
              "flex items-center gap-2 rounded-md px-2 py-1.5 transition-colors",
              isClickable && "cursor-pointer hover:bg-muted/50",
              !isClickable && "opacity-50",
            )}
            onClick={
              isClickable && onStepClick
                ? () => onStepClick(phase)
                : undefined
            }
          >
            <span
              className={cn(
                "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs font-medium",
                idleColor(availability),
              )}
            >
              {idleIcon(availability)}
            </span>
            <div className="flex flex-col leading-tight">
              <span
                className={cn(
                  "text-xs font-medium",
                  isClickable ? "text-foreground" : "text-muted-foreground",
                )}
              >
                {PHASE_LABELS[phase]}
              </span>
              {art?.exists && art.modified && (
                <span className="text-[10px] text-muted-foreground">
                  {formatRelativeTime(art.modified)}
                  {art.count != null && ` (${art.count})`}
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
