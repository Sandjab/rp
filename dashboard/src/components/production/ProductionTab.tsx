import { useCallback, useEffect, useRef, useState } from "react";
import { api, subscribePipelineEvents } from "@/lib/api";
import type {
  ArtifactInfo,
  EditionInfo,
  PhaseName,
  PhaseStatus,
  PipelineEvent,
} from "@/lib/types";
import { PHASE_ORDER } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Stepper } from "./Stepper";
import { StepLauncher } from "./StepLauncher";
import { StepProgress } from "./StepProgress";
import { StepEditor } from "./StepEditor";
import { StepDeploy } from "./StepDeploy";
import { StepImage } from "./StepImage";
import { LogPanel } from "./LogPanel";

// ── Helpers ──────────────────────────────────────────────────────────────────

function initialPhaseStatus(): Record<PhaseName, PhaseStatus> {
  const s = {} as Record<PhaseName, PhaseStatus>;
  for (const p of PHASE_ORDER) s[p] = "pending";
  return s;
}

type PhaseTimes = Record<
  string,
  { start?: number; end?: number; duration?: number }
>;

// ── Component ────────────────────────────────────────────────────────────────

export function ProductionTab() {
  const [edition, setEdition] = useState<EditionInfo | null>(null);
  const [running, setRunning] = useState(false);
  const [phaseStatus, setPhaseStatus] = useState<Record<PhaseName, PhaseStatus>>(
    initialPhaseStatus,
  );
  const [phaseTimes, setPhaseTimes] = useState<PhaseTimes>({});
  const [currentPhase, setCurrentPhase] = useState<PhaseName | null>(null);
  const [logs, setLogs] = useState<PipelineEvent[]>([]);
  const [pipelineDone, setPipelineDone] = useState(false);

  // Artifacts for idle mode
  const [artifacts, setArtifacts] = useState<Record<string, ArtifactInfo>>({});

  // Overwrite confirmation state
  const [confirmPhase, setConfirmPhase] = useState<PhaseName | null>(null);

  // Active idle-mode view (editor/image when clicked from stepper)
  const [idleView, setIdleView] = useState<PhaseName | null>(null);

  // Track elapsed time for running phase
  const [elapsed, setElapsed] = useState(0);
  const elapsedRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const phaseStartRef = useRef<number | null>(null);

  const cleanupSSE = useRef<(() => void) | null>(null);

  // ── Fetch artifacts ──
  const fetchArtifacts = useCallback(async () => {
    try {
      const res = await api.getArtifacts();
      setArtifacts(res.artifacts);
    } catch (err) {
      console.error("Failed to fetch artifacts", err);
    }
  }, []);

  // ── Bootstrap: fetch edition info + check existing run ──
  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        const [ed, status] = await Promise.all([
          api.getNextEdition(),
          api.getPipelineStatus(),
        ]);

        if (cancelled) return;

        setEdition(ed);

        if (status.running && status.run_id) {
          // Restore state from an existing run
          setRunning(true);
          setPhaseStatus(status.phase_status as Record<PhaseName, PhaseStatus>);
          setPhaseTimes(status.phase_times);
          setCurrentPhase(status.current_phase as PhaseName | null);
          connectSSE();
        } else {
          // Idle: fetch artifacts
          fetchArtifacts();
        }
      } catch (err) {
        console.error("Failed to init ProductionTab", err);
      }
    }

    init();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Cleanup SSE on unmount
  useEffect(() => {
    return () => {
      cleanupSSE.current?.();
    };
  }, []);

  // Elapsed timer management
  useEffect(() => {
    if (currentPhase && running) {
      const status = phaseStatus[currentPhase];
      if (status === "running" || status === "resumed") {
        const times = phaseTimes[currentPhase];
        phaseStartRef.current = times?.start ?? Date.now() / 1000;
        setElapsed(0);
        elapsedRef.current = setInterval(() => {
          if (phaseStartRef.current != null) {
            setElapsed(Date.now() / 1000 - phaseStartRef.current);
          }
        }, 1000);
      } else {
        if (elapsedRef.current) clearInterval(elapsedRef.current);
      }
    } else {
      if (elapsedRef.current) clearInterval(elapsedRef.current);
    }
    return () => {
      if (elapsedRef.current) clearInterval(elapsedRef.current);
    };
  }, [currentPhase, running, phaseStatus, phaseTimes]);

  // ── SSE connection ──
  const connectSSE = useCallback(() => {
    // Close previous connection if any
    cleanupSSE.current?.();

    const close = subscribePipelineEvents((event: PipelineEvent) => {
      // Accumulate all events in the log
      setLogs((prev) => [...prev, event]);

      switch (event.type) {
        case "phase_start":
          if (event.phase) {
            setCurrentPhase(event.phase as PhaseName);
            setPhaseStatus((prev) => ({
              ...prev,
              [event.phase!]: "running",
            }));
            setPhaseTimes((prev) => ({
              ...prev,
              [event.phase!]: { start: event.timestamp ? Number(event.timestamp) : Date.now() / 1000 },
            }));
          }
          break;

        case "phase_done":
          if (event.phase) {
            setPhaseStatus((prev) => ({
              ...prev,
              [event.phase!]: "done",
            }));
            setPhaseTimes((prev) => {
              const existing = prev[event.phase!] ?? {};
              const end = event.timestamp ? Number(event.timestamp) : Date.now() / 1000;
              return {
                ...prev,
                [event.phase!]: {
                  ...existing,
                  end,
                  duration: event.duration_s ?? (existing.start ? end - existing.start : undefined),
                },
              };
            });
          }
          break;

        case "phase_error":
          if (event.phase) {
            setPhaseStatus((prev) => ({
              ...prev,
              [event.phase!]: "error",
            }));
          }
          break;

        case "pause":
          if (event.phase) {
            setCurrentPhase(event.phase as PhaseName);
            setPhaseStatus((prev) => ({
              ...prev,
              [event.phase!]: "paused",
            }));
          }
          break;

        case "pipeline_done":
          setRunning(false);
          setCurrentPhase(null);
          setPipelineDone(true);
          // Refresh artifacts after pipeline completes
          fetchArtifacts();
          break;
      }
    });

    cleanupSSE.current = close;
  }, [fetchArtifacts]);

  // ── Handlers ──
  const handleStart = useCallback(
    async (params: {
      date: string;
      styles: string[];
      skip_collect: boolean;
      no_linkedin: boolean;
      no_deploy: boolean;
    }) => {
      // Reset state
      setPhaseStatus(initialPhaseStatus());
      setPhaseTimes({});
      setCurrentPhase(null);
      setLogs([]);
      setPipelineDone(false);
      setRunning(true);
      setIdleView(null);
      setConfirmPhase(null);

      try {
        await api.startPipeline(params);
        connectSSE();
      } catch (err) {
        console.error("Failed to start pipeline", err);
        setRunning(false);
      }
    },
    [connectSSE],
  );

  const handleResume = useCallback(async () => {
    try {
      await api.resumePipeline();
    } catch (err) {
      console.error("Failed to resume pipeline", err);
    }
  }, []);

  // ── Idle step click ──
  const handleStepClick = useCallback(
    (phase: PhaseName) => {
      if (running) return;

      // Interactive phases: show their view directly
      if (phase === "editor") {
        setIdleView("editor");
        setConfirmPhase(null);
        return;
      }
      if (phase === "image") {
        setIdleView("image");
        setConfirmPhase(null);
        return;
      }

      // Auto phases: check if artifacts exist (overwrite warning)
      const art = artifacts[phase];
      if (art?.exists) {
        setConfirmPhase(phase);
        setIdleView(null);
        return;
      }

      // No existing artifact: launch directly
      launchSinglePhase(phase);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [running, artifacts, edition],
  );

  const launchSinglePhase = useCallback(
    async (phase: PhaseName) => {
      if (!edition) return;

      setConfirmPhase(null);
      setIdleView(null);

      // Reset state for single-phase run
      setPhaseStatus(initialPhaseStatus());
      setPhaseTimes({});
      setCurrentPhase(null);
      setLogs([]);
      setPipelineDone(false);
      setRunning(true);

      try {
        await api.runPhase({
          phase,
          date: edition.date,
          styles: edition.styles,
        });
        connectSSE();
      } catch (err) {
        console.error("Failed to run phase", err);
        setRunning(false);
      }
    },
    [edition, connectSSE],
  );

  // ── Determine which main content to show ──
  function renderMainContent() {
    // Overwrite confirmation prompt
    if (confirmPhase && !running) {
      return (
        <div className="flex flex-col items-center justify-center gap-4 py-16">
          <p className="text-sm text-muted-foreground">
            Les donnees existantes seront ecrasees. Continuer ?
          </p>
          <div className="flex gap-3">
            <Button
              variant="outline"
              onClick={() => setConfirmPhase(null)}
            >
              Annuler
            </Button>
            <Button onClick={() => launchSinglePhase(confirmPhase)}>
              Continuer
            </Button>
          </div>
        </div>
      );
    }

    // Idle view: editor
    if (idleView === "editor" && !running) {
      return (
        <StepEditor
          onPublishAndContinue={() => {
            setIdleView(null);
            fetchArtifacts();
          }}
        />
      );
    }

    // Idle view: image
    if (idleView === "image" && !running) {
      return (
        <StepImage
          editionNumber={edition?.number ?? 0}
          editionDate={edition?.date ?? ""}
          onValidate={() => {
            setIdleView(null);
            fetchArtifacts();
          }}
        />
      );
    }

    // Not started yet (idle)
    if (!running && !pipelineDone) {
      if (!edition) {
        return (
          <div className="flex items-center justify-center py-16 text-muted-foreground">
            Chargement...
          </div>
        );
      }
      return <StepLauncher edition={edition} onStart={handleStart} />;
    }

    // Pipeline done
    if (pipelineDone && !running) {
      return (
        <div className="flex flex-col items-center justify-center gap-4 py-16">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-emerald-500/10 text-3xl text-emerald-400">
            &#10003;
          </div>
          <h2 className="text-xl font-semibold">Pipeline termine</h2>
          <p className="text-sm text-muted-foreground">
            L&apos;edition a ete generee avec succes.
          </p>
          <Button
            variant="outline"
            className="mt-4"
            onClick={() => {
              setPipelineDone(false);
              setRunning(false);
              setPhaseStatus(initialPhaseStatus());
              setPhaseTimes({});
              setCurrentPhase(null);
              setLogs([]);
              setIdleView(null);
              fetchArtifacts();
            }}
          >
            Nouvelle edition
          </Button>
        </div>
      );
    }

    // Running — determine what to show based on current phase status
    if (currentPhase) {
      const status = phaseStatus[currentPhase];

      // Paused at editor
      if (currentPhase === "editor" && status === "paused") {
        return <StepEditor onPublishAndContinue={handleResume} />;
      }

      // Paused at image
      if (currentPhase === "image" && status === "paused") {
        return (
          <StepImage
            editionNumber={edition?.number ?? 0}
            editionDate={edition?.date ?? ""}
            onValidate={handleResume}
          />
        );
      }

      // Paused at deploy
      if (currentPhase === "deploy" && status === "paused") {
        return (
          <StepDeploy
            editionNumber={edition?.number ?? 0}
            editionDate={edition?.date ?? ""}
            onDeploy={handleResume}
          />
        );
      }

      // Auto phase running
      if (status === "running" || status === "resumed") {
        // Find the "real" phase for display (skip editorial sub-phases)
        const displayPhase = currentPhase.startsWith("editorial_")
          ? "editorial" as PhaseName
          : currentPhase;
        return <StepProgress phase={displayPhase} elapsed={Math.round(elapsed)} />;
      }
    }

    // Fallback: something is running but we don't have a specific phase yet
    return (
      <div className="flex items-center justify-center py-16 text-muted-foreground">
        Demarrage du pipeline...
      </div>
    );
  }

  const isIdle = !running && !pipelineDone;
  const stepperMode = running || pipelineDone ? "running" : "idle";
  const showLogs = logs.length > 0;

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-1 overflow-hidden">
        {/* Left sidebar: Stepper — always visible */}
        <Stepper
          phaseStatus={phaseStatus}
          phaseTimes={phaseTimes}
          editionNumber={edition?.number}
          editionDate={edition?.date}
          mode={stepperMode}
          artifacts={isIdle ? artifacts : undefined}
          onStepClick={isIdle ? handleStepClick : undefined}
        />

        {/* Main area */}
        <div className="flex-1 overflow-y-auto">{renderMainContent()}</div>
      </div>

      {/* Bottom: LogPanel */}
      {showLogs && (
        <div className="h-[200px] border-t border-border">
          <LogPanel logs={logs} />
        </div>
      )}
    </div>
  );
}
