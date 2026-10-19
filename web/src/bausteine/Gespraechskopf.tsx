/** Die Kopfzeile über einem Gespräch.
 *
 * Sagt, wo man ist (Titel, Bereich) und was gerade gilt (Websuche, Agent),
 * und hält die Aktionen, die sich auf das ganze Gespräch beziehen: umbenennen
 * (Klick auf den Titel), als Markdown sichern, löschen, neu anfangen.
 */

import { useEffect, useRef, useState } from "react";
import { Zeichen } from "./Zeichen";
import "./Gespraechskopf.css";

interface Eigenschaften {
  bereichName: string;
  titel: string | null;
  /** Ohne Sitzung (neues Gespräch) gibt es nichts umzubenennen oder zu löschen. */
  hatSitzung: boolean;
  hatNachrichten: boolean;
  agent: string | null;
  websuche: boolean;
  /** Denkaufwand (Stufenname), wenn an. */
  denken?: string;
  aufUmbenennen: (titel: string) => void;
  aufExport: () => void;
  aufLoeschen: () => void;
  aufNeu: () => void;
  aufVerlauf: () => void;
}

export function Gespraechskopf({
  bereichName,
  titel,
  hatSitzung,
  hatNachrichten,
  agent,
  websuche,
  denken,
  aufUmbenennen,
  aufExport,
  aufLoeschen,
  aufNeu,
  aufVerlauf,
}: Eigenschaften) {
  const [bearbeitet, setBearbeitet] = useState(false);
  const [entwurf, setEntwurf] = useState(titel ?? "");
  const feldRef = useRef<HTMLInputElement>(null);

  useEffect(() => setEntwurf(titel ?? ""), [titel]);
  useEffect(() => {
    if (bearbeitet) feldRef.current?.select();
  }, [bearbeitet]);

  function fertig(speichern: boolean) {
    setBearbeitet(false);
    const t = entwurf.trim();
    if (speichern && t && t !== titel) aufUmbenennen(t);
    else setEntwurf(titel ?? "");
  }

  return (
    <header className="gkopf">
      <button type="button" className="gkopf-knopf gkopf-verlauf" onClick={aufVerlauf} aria-label="Verlauf öffnen">
        <Zeichen name="menu" groesse={16} />
      </button>

      <div className="gkopf-titel">
        <span className="gkopf-bereich">{bereichName}</span>
        {bearbeitet ? (
          <input
            ref={feldRef}
            className="gkopf-feld"
            value={entwurf}
            onChange={(e) => setEntwurf(e.target.value)}
            onBlur={() => fertig(true)}
            onKeyDown={(e) => {
              if (e.key === "Enter") fertig(true);
              if (e.key === "Escape") fertig(false);
            }}
            maxLength={100}
            aria-label="Titel des Gesprächs"
          />
        ) : hatSitzung ? (
          <button type="button" className="gkopf-name" onClick={() => setBearbeitet(true)} title="Klicken zum Umbenennen">
            <span key={titel}>{titel || "Ohne Titel"}</span>
            <Zeichen name="stift" groesse={12} />
          </button>
        ) : (
          <span className="gkopf-name ist-neu">{hatNachrichten ? "Neues Gespräch" : "Neues Gespräch"}</span>
        )}
        {websuche && (
          <span className="gkopf-marke ist-web">
            <Zeichen name="web" groesse={11} />
            Websuche
          </span>
        )}
        {denken && (
          <span className="gkopf-marke ist-denken">
            <Zeichen name="denken" groesse={11} />
            {denken}
          </span>
        )}
        {agent && (
          <span className="gkopf-marke" key={agent}>
            <Zeichen name="agent" groesse={11} />
            {agent}
          </span>
        )}
      </div>

      <div className="gkopf-aktionen">
        {hatNachrichten && (
          <button type="button" className="gkopf-knopf" onClick={aufExport} title="Als Markdown sichern">
            <Zeichen name="export" groesse={15} />
          </button>
        )}
        {hatSitzung && (
          <button type="button" className="gkopf-knopf ist-gefahr" onClick={aufLoeschen} title="Gespräch löschen">
            <Zeichen name="muell" groesse={15} />
          </button>
        )}
        <button type="button" className="gkopf-knopf ist-neu" onClick={aufNeu} title="Neues Gespräch (Strg Alt N)">
          <Zeichen name="neu" groesse={15} />
          <span>Neu</span>
        </button>
      </div>
    </header>
  );
}
