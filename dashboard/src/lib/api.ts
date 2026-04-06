import type { EditionInfo, PipelineEvent, PipelineStatus, VariantArticle } from "./types";

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
