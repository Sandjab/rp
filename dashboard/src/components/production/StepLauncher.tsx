import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import type { EditionInfo } from "@/lib/types";

interface StartParams {
  date: string;
  styles: string[];
  skip_collect: boolean;
  no_linkedin: boolean;
  no_deploy: boolean;
}

interface StepLauncherProps {
  edition: EditionInfo;
  onStart: (params: StartParams) => void;
}

const AVAILABLE_STYLES = ["deep", "angle", "focused"] as const;

function formatDateFR(dateStr: string) {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("fr-FR", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export function StepLauncher({ edition, onStart }: StepLauncherProps) {
  const [date, setDate] = useState(edition.date);
  const [styles, setStyles] = useState<string[]>(edition.styles);
  const [skipCollect, setSkipCollect] = useState(false);
  const [noLinkedin, setNoLinkedin] = useState(false);
  const [noDeploy, setNoDeploy] = useState(false);

  function toggleStyle(style: string) {
    setStyles((prev) =>
      prev.includes(style) ? prev.filter((s) => s !== style) : [...prev, style],
    );
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onStart({
      date,
      styles,
      skip_collect: skipCollect,
      no_linkedin: noLinkedin,
      no_deploy: noDeploy,
    });
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="mx-auto flex max-w-lg flex-col items-center gap-6 py-12"
    >
      {/* Date picker */}
      <div className="flex flex-col items-center gap-1">
        <label htmlFor="edition-date" className="text-sm text-muted-foreground">
          Date de publication
        </label>
        <input
          id="edition-date"
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="rounded-md border border-input bg-transparent px-3 py-1.5 text-sm text-foreground outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
        />
        <span className="text-xs text-muted-foreground">{formatDateFR(date)}</span>
      </div>

      {/* Style badges */}
      <div className="flex flex-col items-center gap-2">
        <span className="text-sm text-muted-foreground">Styles editoriaux</span>
        <div className="flex gap-2">
          {AVAILABLE_STYLES.map((style) => (
            <Badge
              key={style}
              variant={styles.includes(style) ? "default" : "outline"}
              className="cursor-pointer select-none"
              onClick={() => toggleStyle(style)}
            >
              {style}
            </Badge>
          ))}
        </div>
      </div>

      {/* Checkboxes */}
      <div className="flex flex-col gap-3">
        <label className="flex items-center gap-2 text-sm">
          <Checkbox
            checked={skipCollect}
            onCheckedChange={(v) => setSkipCollect(v === true)}
          />
          Sauter la collecte
        </label>
        <label className="flex items-center gap-2 text-sm">
          <Checkbox
            checked={noLinkedin}
            onCheckedChange={(v) => setNoLinkedin(v === true)}
          />
          Sans LinkedIn
        </label>
        <label className="flex items-center gap-2 text-sm">
          <Checkbox
            checked={noDeploy}
            onCheckedChange={(v) => setNoDeploy(v === true)}
          />
          Sans deploiement
        </label>
      </div>

      {/* Launch button */}
      <Button type="submit" size="lg" className="mt-4 text-base" disabled={styles.length === 0}>
        Lancer l&apos;edition #{edition.number}
      </Button>
    </form>
  );
}
