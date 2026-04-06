import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ArchiveEdition } from "@/lib/types";

export function ArchivesTab() {
  const [editions, setEditions] = useState<ArchiveEdition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getArchives()
      .then((data) => {
        // Sort by date descending (newest first)
        const sorted = [...data.editions].sort((a, b) =>
          b.date.localeCompare(a.date),
        );
        setEditions(sorted);
        setLoading(false);
      })
      .catch((err) => {
        setError(String(err));
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-muted-foreground">
        Chargement des archives...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64 text-red-500">
        {error}
      </div>
    );
  }

  if (editions.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-muted-foreground">
        Aucune edition archivee
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="divide-y divide-border rounded-lg border border-border">
        {editions.map((edition) => (
          <a
            key={`${edition.date}-${edition.number}`}
            href={`https://sandjab.github.io/rp/editions/archives/${edition.date}.html`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-baseline gap-4 px-5 py-4 transition-colors hover:bg-muted/50"
          >
            {/* Edition number */}
            <span
              className="shrink-0 text-sm text-muted-foreground"
              style={{
                fontFamily: "'JetBrains Mono', ui-monospace, monospace",
              }}
            >
              N&deg;{edition.number}
            </span>

            {/* Date */}
            <span
              className="shrink-0 text-sm text-muted-foreground"
              style={{
                fontFamily: "'JetBrains Mono', ui-monospace, monospace",
              }}
            >
              {edition.date}
            </span>

            {/* Title */}
            <span className="flex-1 truncate text-sm text-foreground">
              {edition.title}
            </span>

            {/* Article count */}
            <span
              className="shrink-0 text-xs text-muted-foreground"
              style={{
                fontFamily: "'JetBrains Mono', ui-monospace, monospace",
              }}
            >
              {edition.article_count} art.
            </span>
          </a>
        ))}
      </div>
    </div>
  );
}
