import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import type { ComponentProps } from "react";

interface CopyLinkedInButtonProps {
  size?: ComponentProps<typeof Button>["size"];
}

export function CopyLinkedInButton({ size = "default" }: CopyLinkedInButtonProps) {
  const [status, setStatus] = useState<"idle" | "loading" | "copied" | "error">("idle");

  const handleCopy = useCallback(async () => {
    setStatus("loading");
    try {
      const { text } = await api.getLinkedInPost();
      await navigator.clipboard.writeText(text);
      setStatus("copied");
      setTimeout(() => setStatus("idle"), 2000);
    } catch {
      setStatus("error");
      setTimeout(() => setStatus("idle"), 2000);
    }
  }, []);

  return (
    <Button variant="outline" size={size} onClick={handleCopy} disabled={status === "loading"}>
      {status === "copied"
        ? "Copie !"
        : status === "error"
          ? "Erreur"
          : "Copier le post LinkedIn"}
    </Button>
  );
}
