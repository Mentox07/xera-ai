/** Was das Modell gerade tut — unten in der Leiste.
 *
 * Seit Oktober 2026 rechnet der Server für mehrere Personen zugleich (Slots
 * mit gemeinsamem Kontextspeicher). Wer fragt, während jemand anderes eine Antwort bekommt,
 * wartet. Ohne diese Anzeige sieht das aus wie ein Fehler.
 *
 * Fragt alle vier Sekunden, aber nur solange der Tab sichtbar ist — ein
 * vergessener Tab im Hintergrund soll den Server nicht beschäftigen.
 */

import { useEffect, useState } from "react";
import { fensterSetzen } from "../daten/useGespraech";
import "./Modellstatus.css";

interface Status {
  erreichbar: boolean;
  beschaeftigt: number;
  wartend: number;
  schreiben_ts: number | null;
}

export function Modellstatus({ breit }: { breit: boolean }) {
  const [status, setStatus] = useState<Status | null>(null);

  useEffect(() => {
    let aus = false;
    let zeitgeber: ReturnType<typeof setTimeout> | undefined;
    // Nur eine Abfrage-Schleife. Vorher startete jeder Wechsel zurück in den
    // Tab eine weitere — nach zehn Wechseln fragten elf Schleifen parallel
    // (Chat 512: 11 Abfragen in derselben Sekunde).
    let unterwegs = false;
    async function holen() {
      clearTimeout(zeitgeber);
      if (unterwegs) return;
      unterwegs = true;
      if (document.visibilityState === "visible") {
        try {
          const r = await fetch("/api/modellstatus", { credentials: "include" });
          if (r.ok && !aus) {
            const s = await r.json();
            fensterSetzen(s.fenster);
            setStatus(s);
          }
        } catch {
          if (!aus) setStatus({ erreichbar: false, beschaeftigt: 0, wartend: 0, schreiben_ts: null });
        }
      }
      unterwegs = false;
      if (!aus) zeitgeber = setTimeout(holen, 4000);
    }
    void holen();
    const sichtbar = () => document.visibilityState === "visible" && void holen();
    document.addEventListener("visibilitychange", sichtbar);
    return () => {
      aus = true;
      clearTimeout(zeitgeber);
      document.removeEventListener("visibilitychange", sichtbar);
    };
  }, []);

  if (!status) return null;

  const zustand = !status.erreichbar
    ? "aus"
    : status.wartend > 0
      ? "wartet"
      : status.beschaeftigt > 0
        ? "rechnet"
        : "bereit";
  const text = {
    aus: "Modell nicht erreichbar",
    wartet: `belegt · ${status.wartend} warten`,
    rechnet: "rechnet gerade",
    bereit: status.schreiben_ts ? `bereit · ${Math.round(status.schreiben_ts)} t/s` : "bereit",
  }[zustand];

  return (
    <div className={`modellstatus ist-${zustand}${breit ? " breit" : ""}`} role="status" title={`Modell: ${text}`}>
      <span className="modellstatus-punkt" aria-hidden="true" />
      {breit ? <span className="modellstatus-text">{text}</span> : <span className="nur-vorlesen">Modell: {text}</span>}
    </div>
  );
}
