import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { VariantArticle } from "@/lib/types";

interface VariantData {
  name: string;
  articles: VariantArticle[];
  dirty: boolean;
}

interface CopyPopover {
  visible: boolean;
  sourceVariant: string;
  field: "editorial_title" | "editorial_summary";
  anchorRect: DOMRect;
}

interface StepEditorProps {
  onPublishAndContinue: () => void;
}

export function StepEditor({ onPublishAndContinue }: StepEditorProps) {
  const [variants, setVariants] = useState<VariantData[]>([]);
  const [published, setPublished] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [focusedVariant, setFocusedVariant] = useState<string | null>(null);
  const [copyPopover, setCopyPopover] = useState<CopyPopover | null>(null);
  const textareaRefs = useRef<Map<string, HTMLTextAreaElement>>(new Map());

  // Load variants on mount
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { variants: names, published: pub } = await api.getVariants();
        const loaded: VariantData[] = [];
        for (const name of names) {
          const articles = await api.getVariant(name);
          loaded.push({ name, articles, dirty: false });
        }
        if (!cancelled) {
          setVariants(loaded);
          setPublished(pub);
          setLoading(false);
        }
      } catch (err) {
        console.error("Failed to load variants", err);
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // Auto-resize textareas
  const autoResize = useCallback((el: HTMLTextAreaElement | null) => {
    if (!el) return;
    el.style.height = "auto";
    el.style.height = el.scrollHeight + "px";
  }, []);

  // Update slot 0 field for a variant
  function updateField(variantName: string, field: "editorial_title" | "editorial_summary", value: string) {
    setVariants((prev) =>
      prev.map((v) => {
        if (v.name !== variantName) return v;
        const articles = [...v.articles];
        articles[0] = { ...articles[0], [field]: value };
        return { ...v, articles, dirty: true };
      }),
    );
  }

  // Save a variant
  async function saveVariant(variantName: string) {
    const variant = variants.find((v) => v.name === variantName);
    if (!variant) return;
    await api.saveVariant(variantName, variant.articles);
    setVariants((prev) =>
      prev.map((v) => (v.name === variantName ? { ...v, dirty: false } : v)),
    );
  }

  // Publish a variant
  async function publishAndContinue(variantName: string) {
    const variant = variants.find((v) => v.name === variantName);
    if (!variant) return;
    if (variant.dirty) {
      await api.saveVariant(variantName, variant.articles);
    }
    await api.publishVariant(variantName);
    setPublished(variantName);
    onPublishAndContinue();
  }

  // Open copy popover
  function openCopyPopover(
    e: React.MouseEvent,
    sourceVariant: string,
    field: "editorial_title" | "editorial_summary",
  ) {
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    setCopyPopover({ visible: true, sourceVariant, field, anchorRect: rect });
  }

  // Execute copy from source to target
  function executeCopy(targetVariant: string) {
    if (!copyPopover) return;
    const { sourceVariant, field } = copyPopover;
    const source = variants.find((v) => v.name === sourceVariant);
    if (!source) return;
    const value = source.articles[0]?.[field] ?? "";
    updateField(targetVariant, field, value);
    setCopyPopover(null);
  }

  // Close popover on outside click
  useEffect(() => {
    if (!copyPopover?.visible) return;
    function handleClick() {
      setCopyPopover(null);
    }
    // Delay listener to avoid immediate close from the opening click
    const timer = setTimeout(() => {
      window.addEventListener("click", handleClick);
    }, 0);
    return () => {
      clearTimeout(timer);
      window.removeEventListener("click", handleClick);
    };
  }, [copyPopover?.visible]);

  // Ctrl+S shortcut
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        if (focusedVariant) {
          saveVariant(focusedVariant);
        }
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusedVariant, variants]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-muted-foreground">
        Chargement des variantes...
      </div>
    );
  }

  if (variants.length === 0) {
    return (
      <div className="flex items-center justify-center py-16 text-muted-foreground">
        Aucune variante disponible
      </div>
    );
  }

  return (
    <div className="relative flex gap-4 overflow-x-auto p-2">
      {/* Copy target popover */}
      {copyPopover?.visible && (
        <div
          className="fixed z-50 rounded border border-border bg-popover px-1 py-1 shadow-md"
          style={{
            top: copyPopover.anchorRect.bottom + 4,
            left: copyPopover.anchorRect.left,
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {variants
            .filter((v) => v.name !== copyPopover.sourceVariant)
            .map((v) => (
              <button
                key={v.name}
                type="button"
                className="block w-full rounded px-3 py-1 text-left font-mono text-xs hover:bg-accent hover:text-accent-foreground"
                onClick={() => executeCopy(v.name)}
              >
                {v.name}
              </button>
            ))}
        </div>
      )}

      {variants.map((variant) => {
        const synthesis = variant.articles[0];
        const isPublished = published === variant.name;

        return (
          <div
            key={variant.name}
            className={cn(
              "flex flex-1 flex-col gap-3 rounded-lg border p-4",
              variant.dirty && "bg-amber-500/5",
              isPublished && "border-b-4 border-b-emerald-500",
            )}
            onFocus={() => setFocusedVariant(variant.name)}
          >
            {/* Header */}
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                {variant.name}
              </span>
              <div className="flex gap-1.5">
                <Button
                  variant="outline"
                  size="xs"
                  onClick={() => saveVariant(variant.name)}
                  disabled={!variant.dirty}
                >
                  Enregistrer
                </Button>
                <Button
                  variant="default"
                  size="xs"
                  onClick={() => publishAndContinue(variant.name)}
                >
                  Publier &amp; Continuer &rarr;
                </Button>
              </div>
            </div>

            {/* Title + copy button */}
            <div className="group/title relative flex flex-col gap-1">
              <input
                type="text"
                value={synthesis?.editorial_title ?? ""}
                onChange={(e) => updateField(variant.name, "editorial_title", e.target.value)}
                placeholder="Titre editorial"
                className="rounded border border-input bg-transparent px-2 py-1 font-serif text-lg outline-none focus-visible:border-ring focus-visible:ring-1 focus-visible:ring-ring/50"
              />
              {variants.length > 1 && (
                <button
                  type="button"
                  className="self-start text-[11px] font-mono text-muted-foreground opacity-0 transition-opacity hover:text-foreground group-hover/title:opacity-100"
                  onClick={(e) => openCopyPopover(e, variant.name, "editorial_title")}
                >
                  copier titre &rarr;
                </button>
              )}
            </div>

            {/* Summary textarea + copy button */}
            <div className="group/summary relative flex flex-1 flex-col gap-1">
              <textarea
                ref={(el) => {
                  if (el) {
                    textareaRefs.current.set(variant.name, el);
                    autoResize(el);
                  }
                }}
                value={synthesis?.editorial_summary ?? ""}
                onChange={(e) => {
                  updateField(variant.name, "editorial_summary", e.target.value);
                  autoResize(e.target);
                }}
                placeholder="Synthese editoriale"
                className="min-h-[120px] resize-none rounded border border-input bg-transparent px-2 py-1.5 text-sm leading-relaxed outline-none focus-visible:border-ring focus-visible:ring-1 focus-visible:ring-ring/50"
              />
              {variants.length > 1 && (
                <button
                  type="button"
                  className="self-start text-[11px] font-mono text-muted-foreground opacity-0 transition-opacity hover:text-foreground group-hover/summary:opacity-100"
                  onClick={(e) => openCopyPopover(e, variant.name, "editorial_summary")}
                >
                  copier edito &rarr;
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
