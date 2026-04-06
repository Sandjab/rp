import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

export function ConfigTab() {
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Load config on mount
  useEffect(() => {
    api
      .getConfig()
      .then((data) => {
        setContent(data.content);
        setLoading(false);
      })
      .catch((err) => {
        setStatus({ type: "error", message: String(err) });
        setLoading(false);
      });
  }, []);

  const save = useCallback(async () => {
    setSaving(true);
    setStatus(null);
    try {
      await api.saveConfig(content);
      setStatus({ type: "success", message: "Configuration sauvegardée" });
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Erreur inconnue";
      setStatus({ type: "error", message });
    } finally {
      setSaving(false);
    }
  }, [content]);

  // Ctrl+S shortcut
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        save();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [save]);

  // Auto-dismiss success after 3s
  useEffect(() => {
    if (status?.type === "success") {
      const t = setTimeout(() => setStatus(null), 3000);
      return () => clearTimeout(t);
    }
  }, [status]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-muted-foreground">
        Chargement de la configuration...
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col min-h-0">
      {/* Sticky header bar */}
      <div className="sticky top-0 z-10 flex items-center gap-3 bg-background pb-3 border-b border-border mb-3">
        <button
          onClick={save}
          disabled={saving}
          className="rounded-md bg-foreground px-4 py-2 text-sm font-medium text-background hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {saving ? "Sauvegarde..." : "Sauvegarder"}
        </button>
        <span className="text-xs text-muted-foreground">Ctrl+S</span>

        {status && (
          <span
            className={`text-sm ${
              status.type === "error"
                ? "text-red-500"
                : "text-green-600 dark:text-green-400"
            }`}
          >
            {status.message}
          </span>
        )}
      </div>

      {/* YAML editor */}
      <textarea
        ref={textareaRef}
        value={content}
        onChange={(e) => setContent(e.target.value)}
        spellCheck={false}
        className="flex-1 w-full resize-none rounded-md border border-border bg-muted/50 p-4 font-mono text-sm leading-relaxed text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
        placeholder="# YAML configuration..."
      />
    </div>
  );
}
