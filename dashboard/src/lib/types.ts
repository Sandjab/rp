// ── Phase types ──────────────────────────────────────────────────────────────

export type PhaseStatus =
  | "pending"
  | "running"
  | "done"
  | "error"
  | "skipped"
  | "paused"
  | "resumed";

export type PhaseName =
  | "websearch"
  | "collect"
  | "editorial"
  | "editor"
  | "image"
  | "html"
  | "deploy";

export const PHASE_ORDER: PhaseName[] = [
  "websearch",
  "collect",
  "editorial",
  "editor",
  "image",
  "html",
  "deploy",
];

export const PHASE_LABELS: Record<PhaseName, string> = {
  websearch: "Recherche web",
  collect: "Collecte RSS",
  editorial: "Redaction",
  editor: "Choix variante",
  image: "Image LinkedIn",
  html: "Generation HTML",
  deploy: "Deploiement",
};

// ── API response types ───────────────────────────────────────────────────────

export interface EditionInfo {
  number: number;
  date: string;
  title: string;
  styles: string[];
}

export interface PipelineStatus {
  running: boolean;
  run_id: string | null;
  current_phase: PhaseName | null;
  phase_status: Record<PhaseName, PhaseStatus>;
  phase_times: Record<string, { start?: number; end?: number; duration?: number }>;
  date: string;
  styles: string[];
  aborted: boolean;
}

export interface PipelineEvent {
  type:
    | "phase_start"
    | "phase_done"
    | "phase_error"
    | "log"
    | "pause"
    | "pipeline_done"
    | "no_run";
  phase?: PhaseName;
  line?: string;
  stream?: "stdout" | "stderr";
  duration_s?: number;
  exit_code?: number;
  error?: string;
  reason?: string;
  timestamp?: string;
}

// ── Artifact / resume types ─────────────────────────────────────────────────

export interface ArtifactInfo {
  exists: boolean;
  modified?: string;
  count?: number;
}

export type PhaseAvailability = "available" | "blocked" | "done";

// ── Variant / article types ──────────────────────────────────────────────────

export interface VariantArticle {
  editorial_title?: string;
  editorial_summary?: string;
  title?: string;
  source?: string;
  url?: string;
  comment?: string;
  [key: string]: unknown;
}
