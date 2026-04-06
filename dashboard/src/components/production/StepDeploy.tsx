import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";

interface StepDeployProps {
  editionNumber: number;
  editionDate: string;
  onDeploy: () => void;
}

export function StepDeploy({ editionNumber, editionDate, onDeploy }: StepDeployProps) {
  const [confirming, setConfirming] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Clear timeout on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const handleClick = useCallback(() => {
    if (confirming) {
      // Second click: confirmed
      if (timerRef.current) clearTimeout(timerRef.current);
      setConfirming(false);
      onDeploy();
    } else {
      // First click: enter confirmation state
      setConfirming(true);
      timerRef.current = setTimeout(() => {
        setConfirming(false);
      }, 3000);
    }
  }, [confirming, onDeploy]);

  return (
    <div className="flex flex-col items-center gap-6 py-16">
      <h2 className="text-xl font-semibold">
        Deployer l&apos;edition #{editionNumber}
      </h2>

      <div className="flex flex-col items-center gap-1 text-sm text-muted-foreground">
        <span>Date : {editionDate}</span>
        <span>
          Cible :{" "}
          <a
            href="https://sandjab.github.io/rp/"
            target="_blank"
            rel="noopener noreferrer"
            className="underline underline-offset-2 hover:text-foreground"
          >
            sandjab.github.io/rp/
          </a>
        </span>
      </div>

      <Button
        size="lg"
        variant={confirming ? "destructive" : "default"}
        className="mt-4 text-base"
        onClick={handleClick}
      >
        {confirming ? "Confirmer le deploy ?" : "Deployer"}
      </Button>
    </div>
  );
}
