/** Helfer für Bewegung, die nicht allein mit CSS geht.
 *
 * Alles andere steht in `bewegung.css`. Hier nur, was JavaScript braucht:
 * wissen, wann etwas ins Bild kommt, und Zahlen hochzählen.
 *
 * Jede Funktion fragt `bewegungAus()` — wer im System „Bewegung reduzieren“
 * eingestellt hat, bekommt sofort den Endzustand.
 */

import { useEffect, useRef, useState } from "react";

export function bewegungAus(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Hängt `sichtbar` an, sobald das Element ins Bild scrollt — einmal, nicht
 *  bei jedem Vorbeiscrollen wieder. Wer zurückscrollt, will lesen, nicht
 *  noch einmal zuschauen. */
export function useEinblenden<T extends HTMLElement>(schwelle = 0.18) {
  const ref = useRef<T>(null);
  const [sichtbar, setSichtbar] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (bewegungAus() || !("IntersectionObserver" in window)) {
      setSichtbar(true);
      return;
    }
    const beobachter = new IntersectionObserver(
      ([eintrag]) => {
        if (eintrag?.isIntersecting) {
          setSichtbar(true);
          beobachter.disconnect();
        }
      },
      { threshold: schwelle, rootMargin: "0px 0px -8% 0px" },
    );
    beobachter.observe(el);
    return () => beobachter.disconnect();
  }, [schwelle]);

  return { ref, sichtbar };
}

/** Zählt von 0 auf `ziel`, sobald `los` wahr wird. Langsam am Ende, damit die
 *  letzte Stelle lesbar einrastet statt vorbeizufliegen. */
export function useZaehler(ziel: number, los: boolean, dauerMs = 1400): number {
  const [wert, setWert] = useState(0);

  useEffect(() => {
    if (!los) return;
    if (bewegungAus()) {
      setWert(ziel);
      return;
    }
    let start: number | null = null;
    let rahmen = 0;
    const schritt = (jetzt: number) => {
      start ??= jetzt;
      const t = Math.min(1, (jetzt - start) / dauerMs);
      const weich = 1 - Math.pow(1 - t, 4);
      setWert(Math.round(ziel * weich));
      if (t < 1) rahmen = requestAnimationFrame(schritt);
    };
    rahmen = requestAnimationFrame(schritt);
    return () => cancelAnimationFrame(rahmen);
  }, [ziel, los, dauerMs]);

  return wert;
}
