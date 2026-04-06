import { useEffect, useRef } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import type { PipelineEvent } from "@/lib/types";

interface LogPanelProps {
  logs: PipelineEvent[];
}

function eventColor(event: PipelineEvent) {
  switch (event.type) {
    case "phase_start":
      return "text-blue-400";
    case "phase_done":
      return "text-emerald-400";
    case "phase_error":
      return "text-red-400";
    case "pause":
      return "text-amber-400";
    case "pipeline_done":
      return "text-emerald-400";
    case "log":
      return event.stream === "stderr" ? "text-amber-400" : "text-foreground/80";
    default:
      return "text-muted-foreground";
  }
}

function formatEvent(event: PipelineEvent): string {
  switch (event.type) {
    case "phase_start":
      return `▶ ${event.phase}`;
    case "phase_done":
      return `✓ ${event.phase}${event.duration_s != null ? ` (${Math.round(event.duration_s)}s)` : ""}`;
    case "phase_error":
      return `✗ ${event.phase} : ${event.error ?? `exit ${event.exit_code}`}`;
    case "pause":
      return `⏸ ${event.phase} — en attente`;
    case "pipeline_done":
      return `● Pipeline terminé`;
    case "no_run":
      return `-- Aucun pipeline en cours`;
    case "log":
      return event.line ?? "";
    default:
      return JSON.stringify(event);
  }
}

export function LogPanel({ logs }: LogPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new log entries
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs.length]);

  return (
    <ScrollArea className="h-full">
      <div className="p-2 font-mono text-xs leading-relaxed">
        {logs.map((event, i) => (
          <div key={i} className={cn("whitespace-pre-wrap", eventColor(event))}>
            {formatEvent(event)}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  );
}
