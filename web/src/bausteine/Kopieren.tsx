/** Kopieren mit Rückmeldung am Knopf selbst (Einstellungen → CLI, Seite „CLI“). */

import { useState } from "react";

export function Kopieren({ text, className = "cli-kopieren" }: { text: string; className?: string }) {
  const [kopiert, setKopiert] = useState(false);
  async function los() {
    try {
      await navigator.clipboard.writeText(text);
      setKopiert(true);
      window.setTimeout(() => setKopiert(false), 1600);
    } catch {
      /* ohne Zwischenablage (http, alter Browser) bleibt der Text zum Markieren da */
    }
  }
  return (
    <button type="button" className={className + (kopiert ? " ist-kopiert" : "")} onClick={los}>
      {kopiert ? "kopiert" : "kopieren"}
    </button>
  );
}
