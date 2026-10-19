/** Anhänge: Bilder und Dokumente, die mit einer Frage mitgehen.
 *
 * Bilder gehen als `image_url`-Teil direkt in die Nachricht (das Modell sieht
 * sie selbst, rund zehn Sekunden je Bild). Dokumente gehen erst an
 * `/api/upload`, das den Text herauszieht; der Text geht dann als Textteil mit,
 * und der gespeicherte Name, damit ein Agent die Datei später noch einmal
 * lesen kann.
 */

import { api } from "./api";

export interface Anhang {
  id: string;
  art: "bild" | "dokument";
  name: string;
  /** Bilder: verkleinertes Bild als data:-URL, zugleich die Vorschau. */
  bild?: string;
  /** Dokumente: herausgezogener Text. */
  inhalt?: string;
  /** Dokumente: Name, unter dem der Server die Datei abgelegt hat. */
  gespeichert?: string;
  laedt: boolean;
  fehler?: string;
}

export const ERLAUBTE_DATEIEN = "image/*,.pdf,.docx,.xlsx,.xls,.pptx,.txt,.csv,.md,.json,.log,.yaml,.yml";

/** Längste Bildkante. Grösser bringt dem Modell nichts mehr und kostet nur
 *  Zeit beim Einlesen — ein Handyfoto hat 4 000 Pixel und mehr. */
const MAX_KANTE = 1568;

let zaehler = 0;
const neueId = () => `a${Date.now().toString(36)}${(zaehler++).toString(36)}`;

function bildVerkleinern(datei: File): Promise<string> {
  return new Promise((fertig, fehlschlag) => {
    const url = URL.createObjectURL(datei);
    const bild = new Image();
    bild.onload = () => {
      const faktor = Math.min(1, MAX_KANTE / Math.max(bild.width, bild.height));
      const leinwand = document.createElement("canvas");
      leinwand.width = Math.round(bild.width * faktor);
      leinwand.height = Math.round(bild.height * faktor);
      const ctx = leinwand.getContext("2d");
      if (!ctx) return fehlschlag(new Error("Kein Canvas"));
      ctx.drawImage(bild, 0, 0, leinwand.width, leinwand.height);
      URL.revokeObjectURL(url);
      // PNG bleibt PNG (Screenshots mit Text werden als JPEG unscharf),
      // alles andere wird JPEG.
      fertig(datei.type === "image/png" ? leinwand.toDataURL("image/png") : leinwand.toDataURL("image/jpeg", 0.88));
    };
    bild.onerror = () => {
      URL.revokeObjectURL(url);
      fehlschlag(new Error("Bild nicht lesbar"));
    };
    bild.src = url;
  });
}

/** Legt für jede Datei sofort einen Anhang an (mit `laedt`) und meldet ihn
 *  fertig, sobald er verarbeitet ist. So erscheint der Chip gleich, nicht erst
 *  nach dem Hochladen. */
export function anhaengeVerarbeiten(
  dateien: File[],
  aufNeu: (a: Anhang) => void,
  aufFertig: (a: Anhang) => void,
): void {
  for (const datei of dateien) {
    const id = neueId();
    if (datei.type.startsWith("image/")) {
      aufNeu({ id, art: "bild", name: datei.name || "Bild", laedt: true });
      bildVerkleinern(datei)
        .then((bild) => aufFertig({ id, art: "bild", name: datei.name || "Bild", bild, laedt: false }))
        .catch((e: Error) => aufFertig({ id, art: "bild", name: datei.name, laedt: false, fehler: e.message }));
    } else {
      aufNeu({ id, art: "dokument", name: datei.name, laedt: true });
      api
        .hochladen(datei)
        .then((r) =>
          aufFertig({ id, art: "dokument", name: datei.name, inhalt: r.content, gespeichert: r.stored_name, laedt: false }),
        )
        .catch((e: Error) => aufFertig({ id, art: "dokument", name: datei.name, laedt: false, fehler: e.message }));
    }
  }
}

/** Baut den Inhalt der letzten Nachricht für das Backend. */
export function nachrichtenInhalt(text: string, anhaenge: Anhang[]): string | unknown[] {
  const brauchbar = anhaenge.filter((a) => !a.laedt && !a.fehler);
  if (brauchbar.length === 0) return text;
  const teile: unknown[] = [{ type: "text", text }];
  for (const a of brauchbar) {
    if (a.art === "bild" && a.bild) {
      teile.push({ type: "image_url", image_url: { url: a.bild } });
    } else if (a.art === "dokument") {
      teile.push({
        type: "text",
        text: a.inhalt
          ? `[Dokument: ${a.gespeichert ?? a.name}]\n${a.inhalt}`
          : `[Dokument-Datei: ${a.gespeichert ?? a.name}]`,
      });
    }
  }
  return teile;
}
