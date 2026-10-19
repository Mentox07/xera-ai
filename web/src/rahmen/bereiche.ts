/** Die vier Bereiche.
 *
 * An einer Stelle beschrieben, damit Leiste, Befehlspalette und Tastenkürzel
 * nicht drei Fassungen derselben Liste führen — genau daran lief das alte
 * Frontend auseinander, als die Reiter „Code" und „Homelab" an drei Orten
 * unterschiedlich hießen.
 */

import type { BereichsId } from "../daten/typen";

export interface Bereich {
  id: BereichsId;
  name: string;
  /** Was er tut, in einem Satz. Steht in der Palette und beim ersten Besuch. */
  kurz: string;
  /** Der Modus, den das Backend erwartet. */
  modus: string;
  /** Wo das Backend neue Gespräche ablegt — und woher die Liste kommt. */
  ablage: string;
  taste: string;
  /** Braucht die Homelab-Rolle. */
  nurMitRolle?: boolean;
}

export const BEREICHE: Bereich[] = [
  {
    id: "chat",
    name: "Chat",
    kurz: "Fragen, Recherche, Dokumente lesen",
    // Das Modell antwortet selbst und sucht/liest bei Bedarf mit seinen
    // Grundwerkzeugen — keine Agents im Chat (backend/vermittler.py).
    modus: "agents",
    ablage: "chat",
    taste: "1",
  },
  {
    id: "cowork",
    name: "Cowork",
    kurz: "Ein Arbeitsbereich je Vorhaben — Dateien, Notizen, Gespräche",
    modus: "agents",
    ablage: "cowork",
    taste: "2",
  },
  {
    id: "code",
    name: "Code",
    kurz: "Schreiben, prüfen, umbauen",
    modus: "agents",
    ablage: "code",
    taste: "3",
  },
  {
    id: "homelab",
    name: "Homelab",
    kurz: "Server, Container, Netz — mit Werkzeugen, die etwas anfassen",
    modus: "homelab",
    ablage: "homelab",
    taste: "4",
    nurMitRolle: true,
  },
];

/** Welche Bereiche dieser Nutzer sehen darf.
 *
 * Homelab wird nicht ausgegraut, sondern weggelassen. Wer die Rolle nicht
 * hat, soll nicht raten müssen, was ihm fehlt — und die eigentliche Sperre
 * liegt ohnehin im Backend.
 */
export function sichtbareBereiche(hatHomelab: boolean): Bereich[] {
  return BEREICHE.filter((b) => !b.nurMitRolle || hatHomelab);
}

export function bereichNach(id: string | null | undefined): Bereich {
  return BEREICHE.find((b) => b.id === id) ?? BEREICHE[0]!;
}
