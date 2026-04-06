import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { ImageModel } from "@/lib/types";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Loader2Icon } from "lucide-react";

interface StepImageProps {
  editionNumber: number;
  editionDate: string;
  onValidate: () => void;
}

export function StepImage({ editionNumber, editionDate, onValidate }: StepImageProps) {
  const [models, setModels] = useState<ImageModel[]>([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [prompt, setPrompt] = useState("");
  const [loadingPrompt, setLoadingPrompt] = useState(false);
  const [loadingImage, setLoadingImage] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [imageTimestamp, setImageTimestamp] = useState<number | null>(null);
  const [imageInfo, setImageInfo] = useState<{ model: string; duration_s: number } | null>(null);

  const promptDirty = useRef(false);

  // ── Init: fetch models + check existing state ──
  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        // Load models
        const modelData = await api.getImageModels();
        if (cancelled) return;
        setModels(modelData.models);
        setSelectedModel(modelData.default);

        // Check if an image already exists
        const imgRes = await fetch("/api/image/preview", { method: "HEAD" });
        if (!cancelled && imgRes.ok) {
          setImageTimestamp(Date.now());
        }

        // Try to load existing prompt
        const promptRes = await fetch("/api/image/preview?raw=true", { method: "HEAD" });
        if (!cancelled && promptRes.ok) {
          // Image exists, prompt probably exists too — but we don't have a GET endpoint
          // We'll auto-generate if no prompt is loaded
        }

        // Auto-generate prompt if none
        if (!cancelled) {
          setLoadingPrompt(true);
          try {
            const res = await api.generateImagePrompt();
            if (!cancelled) {
              setPrompt(res.prompt);
            }
          } catch (err) {
            if (!cancelled) {
              setError(`Erreur generation prompt: ${err instanceof Error ? err.message : String(err)}`);
            }
          } finally {
            if (!cancelled) setLoadingPrompt(false);
          }
        }
      } catch (err) {
        if (!cancelled) {
          console.error("StepImage init error", err);
        }
      }
    }

    init();
    return () => { cancelled = true; };
  }, []);

  // ── Handlers ──
  const handleRegeneratePrompt = useCallback(async () => {
    setLoadingPrompt(true);
    setError(null);
    try {
      const res = await api.generateImagePrompt();
      setPrompt(res.prompt);
      promptDirty.current = false;
    } catch (err) {
      setError(`Erreur generation prompt: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setLoadingPrompt(false);
    }
  }, []);

  const handleGenerateImage = useCallback(async () => {
    if (!prompt.trim()) return;

    setLoadingImage(true);
    setError(null);

    // Save prompt if modified
    if (promptDirty.current) {
      try {
        await api.saveImagePrompt(prompt);
        promptDirty.current = false;
      } catch {
        // Non-blocking
      }
    }

    try {
      const res = await api.generateImage({ prompt: prompt.trim(), model: selectedModel });
      setImageTimestamp(Date.now());
      setImageInfo({ model: res.model, duration_s: res.duration_s });
    } catch (err) {
      setError(`Erreur generation image: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setLoadingImage(false);
    }
  }, [prompt, selectedModel]);

  const handlePromptChange = useCallback((value: string) => {
    setPrompt(value);
    promptDirty.current = true;
  }, []);

  // Find model alias for display
  const modelAlias = models.find((m) => m.id === (imageInfo?.model ?? selectedModel))?.alias ?? selectedModel;

  return (
    <div className="flex h-full gap-4 p-4">
      {/* ── Left column: Prompt ── */}
      <div className="flex flex-1 flex-col gap-3">
        <label className="text-sm font-semibold text-muted-foreground">
          Prompt d&apos;image
        </label>

        <div className="relative flex-1">
          {loadingPrompt ? (
            <div className="flex h-full items-center justify-center rounded-lg border border-input bg-muted/20">
              <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
              <span className="ml-2 text-sm text-muted-foreground">Generation du prompt...</span>
            </div>
          ) : (
            <textarea
              value={prompt}
              onChange={(e) => handlePromptChange(e.target.value)}
              placeholder="Le prompt d'image apparaitra ici..."
              className="h-full w-full resize-none rounded-lg border border-input bg-transparent px-3 py-2 font-mono text-sm leading-relaxed outline-none focus-visible:border-ring focus-visible:ring-1 focus-visible:ring-ring/50"
            />
          )}
        </div>

        {error && (
          <p className="text-sm text-red-500">{error}</p>
        )}

        <div className="flex flex-wrap items-center gap-2">
          <Select value={selectedModel} onValueChange={setSelectedModel}>
            <SelectTrigger className="w-[220px]">
              <SelectValue placeholder="Modele" />
            </SelectTrigger>
            <SelectContent>
              {models.map((m) => (
                <SelectItem key={m.id} value={m.id}>
                  {m.alias}
                  <span className="ml-1 text-xs text-muted-foreground">({m.family})</span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Button
            variant="outline"
            size="sm"
            onClick={handleRegeneratePrompt}
            disabled={loadingPrompt}
          >
            {loadingPrompt && <Loader2Icon className="mr-1 size-3.5 animate-spin" />}
            Regenerer prompt
          </Button>

          <Button
            size="sm"
            onClick={handleGenerateImage}
            disabled={loadingImage || loadingPrompt || !prompt.trim()}
          >
            {loadingImage && <Loader2Icon className="mr-1 size-3.5 animate-spin" />}
            Generer image
          </Button>
        </div>
      </div>

      {/* ── Right column: Preview ── */}
      <div className="flex w-[400px] shrink-0 flex-col gap-3">
        <label className="text-sm font-semibold text-muted-foreground">
          Preview
        </label>

        <div className="flex flex-1 items-center justify-center overflow-hidden rounded-lg border border-input bg-muted/10">
          {loadingImage ? (
            <div className="flex flex-col items-center gap-2">
              <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Generation en cours...</span>
            </div>
          ) : imageTimestamp ? (
            <img
              src={`/api/image/preview?t=${imageTimestamp}`}
              alt={`Edition #${editionNumber} — ${editionDate}`}
              className="max-h-full max-w-full object-contain"
            />
          ) : (
            <span className="text-sm text-muted-foreground">
              Aucune image generee
            </span>
          )}
        </div>

        {imageInfo && (
          <p className="text-xs text-muted-foreground">
            {modelAlias} — {imageInfo.duration_s}s
          </p>
        )}

        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleGenerateImage}
            disabled={loadingImage || !prompt.trim()}
          >
            {loadingImage && <Loader2Icon className="mr-1 size-3.5 animate-spin" />}
            Regenerer
          </Button>

          <Button
            size="sm"
            className="bg-emerald-600 hover:bg-emerald-700"
            onClick={onValidate}
            disabled={!imageTimestamp}
          >
            Valider &rarr; HTML
          </Button>
        </div>
      </div>
    </div>
  );
}
