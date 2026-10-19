/** Hell oder dunkel.
 *
 * Die bestehende Oberfläche kann beides, also kann es diese auch. Die Wahl
 * liegt im Speicher des Browsers unter demselben Schlüssel wie bisher — wer
 * zwischen alter und neuer Oberfläche wechselt, soll nicht zweimal umstellen
 * müssen.
 *
 * Ohne gespeicherte Wahl gilt, was das Betriebssystem sagt. Erst wer selbst
 * wählt, überschreibt das dauerhaft.
 */

import { useCallback, useEffect, useState } from "react";

export type Thema = "dark" | "light";

const SCHLUESSEL = "xera-theme";

function gespeichert(): Thema | null {
  try {
    const wert = localStorage.getItem(SCHLUESSEL);
    return wert === "dark" || wert === "light" ? wert : null;
  } catch {
    // Privater Modus oder gesperrter Speicher. Dann eben ohne Gedächtnis —
    // das ist kein Grund, die Oberfläche nicht zu starten.
    return null;
  }
}

function vomSystem(): Thema {
  return window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function useThema() {
  const [thema, setThema] = useState<Thema>(() => gespeichert() ?? vomSystem());

  useEffect(() => {
    document.documentElement.dataset.theme = thema;
  }, [thema]);

  // Ändert jemand die Systemeinstellung, folgt die Oberfläche — aber nur,
  // solange keine eigene Wahl getroffen wurde.
  useEffect(() => {
    if (gespeichert()) return;
    const abfrage = window.matchMedia?.("(prefers-color-scheme: light)");
    if (!abfrage) return;
    const auf = () => setThema(vomSystem());
    abfrage.addEventListener("change", auf);
    return () => abfrage.removeEventListener("change", auf);
  }, []);

  const umschalten = useCallback(() => {
    setThema((alt) => {
      const neu: Thema = alt === "dark" ? "light" : "dark";
      try {
        localStorage.setItem(SCHLUESSEL, neu);
      } catch {
        /* siehe oben */
      }
      return neu;
    });
  }, []);

  return { thema, umschalten };
}
