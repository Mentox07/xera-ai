/** Wie voll das Gesprächsfenster ist — und was man dagegen tun kann.
 *
 * Das Modell sieht pro Gespräch nur begrenzt viele Tokens (Fenster je Slot,
 * vom Server gemeldet). Statt still abzubrechen
 * (oder ältere Teile heimlich zu vergessen) zeigt Xera ab 50 % eine kleine
 * Anzeige, ab 75 % einen Hinweis mit zwei Wegen, und fasst ab 85 % selbst
 * zusammen (backend/kontext.py). Der Verlauf bleibt dabei sichtbar — gekürzt
 * wird nur, was das Modell bekommt.
 */

import { useState } from "react";
import type { Kontext } from "../daten/typen";
import { useRueckmeldung } from "./Rueckmeldung";
import { Zeichen } from "./Zeichen";
import "./Kontextanzeige.css";

interface Eigenschaften {
  kontext: Kontext | null;
  laeuft: boolean;
  aufVerdichten: () => Promise<void>;
  aufUebergabe: () => Promise<unknown>;
}

export function Kontextanzeige({ kontext, laeuft, aufVerdichten, aufUebergabe }: Eigenschaften) {
  const { melden } = useRueckmeldung();
  const [arbeitet, setArbeitet] = useState<"verdichten" | "uebergabe" | null>(null);
  if (!kontext) return null;
  const anteil = Math.min(1, kontext.belegt / kontext.max);
  const prozent = Math.round(anteil * 100);
  if (kontext.stufe === "ok" && anteil < 0.5) return null;

  async function ausfuehren(art: "verdichten" | "uebergabe") {
    setArbeitet(art);
    try {
      if (art === "verdichten") {
        await aufVerdichten();
        melden("Älteres ist zusammengefasst — es geht mit mehr Platz weiter.", "gut");
      } else {
        await aufUebergabe();
        melden("Neues Gespräch mit dem bisherigen Stand geöffnet.", "gut");
      }
    } catch (e) {
      melden(e instanceof Error ? e.message : "Hat nicht geklappt", "fehler");
    } finally {
      setArbeitet(null);
    }
  }

  const balken = (
    <span className="kontext-balken" aria-hidden>
      <span style={{ transform: `scaleX(${anteil})` }} />
    </span>
  );

  if (kontext.stufe === "ok") {
    return (
      <div className="kontext ist-still" title={`${kontext.belegt.toLocaleString("de-CH")} von ${kontext.max.toLocaleString("de-CH")} Tokens`}>
        {balken}
        <span>Gespräch zu {prozent} % gefüllt</span>
      </div>
    );
  }

  const verdichtet = kontext.stufe === "verdichtet";
  const knoepfe = (
    <div className="kontext-knoepfe">
      {!verdichtet && (
        <button type="button" className="knopf-still" disabled={laeuft || arbeitet !== null} onClick={() => void ausfuehren("verdichten")}>
          {arbeitet === "verdichten" ? <span className="kontext-kreisel" /> : <Zeichen name="notiz" groesse={13} />}
          Zusammenfassen und weiter
        </button>
      )}
      <button type="button" className="knopf-still" disabled={laeuft || arbeitet !== null} onClick={() => void ausfuehren("uebergabe")}>
        {arbeitet === "uebergabe" ? <span className="kontext-kreisel" /> : <Zeichen name="neu" groesse={13} />}
        Neuer Chat mit Übergabe
      </button>
    </div>
  );

  return (
    <div className={"kontext ist-hinweis" + (kontext.stufe === "voll" ? " ist-voll" : "") + (verdichtet ? " ist-verdichtet" : "")} role="status">
      <div className="kontext-text">
        {balken}
        {verdichtet ? (
          <span>
            <strong>Ältere Teile sind zusammengefasst.</strong> Du siehst weiter alles; das Modell arbeitet mit einer Zusammenfassung plus den letzten Nachrichten.
          </span>
        ) : (
          <span>
            <strong>Das Gespräch wird lang ({prozent} %).</strong> Ab 85 % fasst Xera Älteres selbst zusammen — oder du entscheidest jetzt.
          </span>
        )}
      </div>
      {arbeitet ? <span className="kontext-dauer">Das Zusammenfassen dauert bei langen Gesprächen 1–3 Minuten …</span> : knoepfe}
    </div>
  );
}
