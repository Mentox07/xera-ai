/** Denkaufwand — wie `/effort` in Claude Code (seit 2026-10-19).
 *
 * Vorher gab es nur „Gründlich denken“ an/aus mit festen 4 096 Denk-Tokens; am
 * 18.10. schrieb das Modell damit ein ganzes Snake-Spiel ins Denken, und der Nutzer
 * brach zweimal ab. Jetzt fünf Stufen, jede mit Token- und Zeitgrenze im Backend
 * (backend/aufwand.py). Die Zahlen hier sind nur für die Anzeige.
 */

export type Aufwand = "aus" | "niedrig" | "mittel" | "hoch" | "max";

export const STUFEN: { id: Aufwand; name: string; text: string }[] = [
  { id: "aus", name: "Aus", text: "Antwortet sofort, ohne nachzudenken." },
  { id: "niedrig", name: "Niedrig", text: "Kurz überlegen — höchstens etwa 1 Minute." },
  { id: "mittel", name: "Mittel", text: "Für knifflige Fragen — höchstens etwa 2 Minuten." },
  { id: "hoch", name: "Hoch", text: "Gründlich, für Mathe und schwere Fehler — bis etwa 4 Minuten." },
  { id: "max", name: "Max", text: "So gründlich wie möglich — bis etwa 7 Minuten." },
];

const SCHLUESSEL = "xera-aufwand";

export function aufwandLaden(): Aufwand {
  try {
    const w = localStorage.getItem(SCHLUESSEL);
    if (STUFEN.some((s) => s.id === w)) return w as Aufwand;
  } catch {
    /* privates Fenster, gesperrter Speicher — dann eben „aus“ */
  }
  return "aus";
}

export function aufwandSpeichern(a: Aufwand): void {
  try {
    localStorage.setItem(SCHLUESSEL, a);
  } catch {
    /* siehe oben */
  }
}

const ALIAS: Record<string, Aufwand> = {
  off: "aus", none: "aus", "0": "aus",
  low: "niedrig", "1": "niedrig",
  medium: "mittel", med: "mittel", "2": "mittel",
  high: "hoch", "3": "hoch",
  xhigh: "max", maximum: "max", "4": "max",
};

/** „/effort hoch“ oder „/aufwand max“ im Eingabefeld.
 *  Liefert null, wenn es kein Befehl ist; "?" bei unbekannter Stufe; "liste" ohne Stufe. */
export function aufwandBefehl(text: string): Aufwand | "?" | "liste" | null {
  const m = /^\/(effort|aufwand|denken)(?:\s+(\S+))?\s*$/i.exec(text.trim());
  if (!m) return null;
  const wert = (m[2] ?? "").toLowerCase();
  if (!wert) return "liste";
  if (STUFEN.some((s) => s.id === wert)) return wert as Aufwand;
  return ALIAS[wert] ?? "?";
}

export function aufwandName(a: Aufwand): string {
  return STUFEN.find((s) => s.id === a)?.name ?? a;
}
