import type { ArchiveEdition, ArtifactInfo, EditionInfo, ImageModel, PipelineEvent, PipelineStatus, VariantArticle } from "./types";

// ── Helpers ──────────────────────────────────────────────────────────────────

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(body.error ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// ── API client ───────────────────────────────────────────────────────────────

export const api = {
  /** Get info about the next edition (number, date, styles). */
  getNextEdition(): Promise<EditionInfo> {
    return fetch("/api/edition/next").then((r) => json<EditionInfo>(r));
  },

  /** Get current pipeline status. */
  getPipelineStatus(): Promise<PipelineStatus> {
    return fetch("/api/pipeline/status").then((r) => json<PipelineStatus>(r));
  },

  /** Start a new pipeline run. */
  startPipeline(params: {
    date: string;
    styles: string[];
    skip_collect: boolean;
    no_linkedin: boolean;
    no_deploy: boolean;
    debug?: boolean;
  }): Promise<{ ok: boolean; run_id: string }> {
    return fetch("/api/pipeline/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    }).then((r) => json(r));
  },

  /** Resume a paused pipeline phase. */
  resumePipeline(): Promise<{ ok: boolean; resumed: string }> {
    return fetch("/api/pipeline/resume", {
      method: "POST",
    }).then((r) => json(r));
  },

  /** Abort the running pipeline. */
  abortPipeline(): Promise<{ ok: boolean }> {
    return fetch("/api/pipeline/abort", {
      method: "POST",
    }).then((r) => json(r));
  },

  /** List variant names and currently published variant. */
  getVariants(): Promise<{ variants: string[]; published: string | null }> {
    return fetch("/api/variants").then((r) => json(r));
  },

  /** Get a single variant's editorial data (array of articles). */
  getVariant(name: string): Promise<VariantArticle[]> {
    return fetch(`/api/variant/${encodeURIComponent(name)}`).then((r) =>
      json<VariantArticle[]>(r),
    );
  },

  /** Save (overwrite) a variant's editorial data. */
  saveVariant(name: string, data: VariantArticle[]): Promise<{ ok: boolean }> {
    return fetch(`/api/variant/${encodeURIComponent(name)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then((r) => json(r));
  },

  /** Publish a variant (copy to 02_editorial.json). */
  publishVariant(name: string): Promise<{ ok: boolean; published: string }> {
    return fetch(`/api/publish/${encodeURIComponent(name)}`, {
      method: "POST",
    }).then((r) => json(r));
  },

  /** Get pipeline artifact status (for manual resume). */
  getArtifacts(): Promise<{ artifacts: Record<string, ArtifactInfo> }> {
    return fetch("/api/pipeline/artifacts").then((r) =>
      json<{ artifacts: Record<string, ArtifactInfo> }>(r),
    );
  },

  /** Run a single pipeline phase (manual resume). */
  runPhase(params: { phase: string; date: string; styles?: string[]; debug?: boolean }): Promise<{ ok: boolean; run_id: string }> {
    return fetch("/api/pipeline/run-phase", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    }).then((r) => json(r));
  },

  // ── Image API ─────────────────────────────────────────────────────────

  /** Get available image generation models. */
  getImageModels(): Promise<{ models: ImageModel[]; default: string }> {
    return fetch("/api/image/models").then((r) => json(r));
  },

  /** Generate an image prompt via claude -p. */
  generateImagePrompt(): Promise<{ prompt: string }> {
    return fetch("/api/image/prompt", { method: "POST" }).then((r) => json(r));
  },

  /** Generate an image from a prompt + model. */
  generateImage(params: { prompt: string; model: string }): Promise<{ ok: boolean; model: string; duration_s: number }> {
    return fetch("/api/image/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    }).then((r) => json(r));
  },

  /** Save a manually edited prompt. */
  saveImagePrompt(prompt: string): Promise<{ ok: boolean }> {
    return fetch("/api/image/prompt/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    }).then((r) => json(r));
  },

  // ── Config API ──────────────────────────────────────────────────────

  /** Get YAML config as raw string. */
  getConfig(): Promise<{ content: string }> {
    return fetch("/api/config").then((r) => json<{ content: string }>(r));
  },

  /** Save YAML config. */
  saveConfig(content: string): Promise<{ ok: boolean }> {
    return fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    }).then((r) => json(r));
  },

  // ── LinkedIn API ─────────────────────────────────────────────────────

  /** Get the LinkedIn post text from .pipeline/linkedin/post.txt. */
  getLinkedInPost(): Promise<{ text: string }> {
    return fetch("/api/linkedin/post").then((r) => json<{ text: string }>(r));
  },

  /** Get the LinkedIn comment text from .pipeline/linkedin/comment.txt. */
  getLinkedInComment(): Promise<{ text: string }> {
    return fetch("/api/linkedin/comment").then((r) => json<{ text: string }>(r));
  },

  // ── Archives API ────────────────────────────────────────────────────

  /** Get archived editions from gh-pages manifest. */
  getArchives(): Promise<{ editions: ArchiveEdition[] }> {
    return fetch("/api/archives").then((r) => json<{ editions: ArchiveEdition[] }>(r));
  },
};

// ── SSE subscription ─────────────────────────────────────────────────────────

/**
 * Subscribe to pipeline events via Server-Sent Events.
 * Returns a cleanup function to close the EventSource.
 */
export function subscribePipelineEvents(
  onEvent: (event: PipelineEvent) => void,
): () => void {
  const source = new EventSource("/api/pipeline/events");

  source.onmessage = (msg) => {
    try {
      const data = JSON.parse(msg.data) as PipelineEvent;
      onEvent(data);
    } catch {
      // Ignore unparseable events
    }
  };

  source.onerror = () => {
    // EventSource reconnects automatically; nothing to do here
  };

  return () => source.close();
}
