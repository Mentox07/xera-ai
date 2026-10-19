/** Ein Werkzeugaufruf, mit Freigabe wenn nötig.
 *
 * Der wichtigste Baustein der Oberfläche, obwohl er selten auffällt: Hier
 * entscheidet jemand, ob etwas auf einem echten Server passiert. Deshalb:
 *
 * * Die **Stufe** steht als Wort da, nicht nur als Farbe. „ADMIN" in Rot und
 *   „READ" in Grün sind für einen Teil der Leute dasselbe Grau.
 * * Die **Argumente sind offen sichtbar**, nicht eingeklappt. Wer freigibt,
 *   ohne zu sehen was, gibt nichts frei — er klickt weiter.
 * * **Ablehnen ist der ruhige Weg**, Freigeben der betonte. Nicht umgekehrt.
 */

import { useState } from "react";
import type { Stufe, Werkzeugaufruf } from "../daten/typen";
import { Zeichen } from "./Zeichen";
import "./Werkzeugblock.css";

const STUFENTEXT: Record<Stufe, string> = {
  READ: "liest nur",
  WRITE: "verändert etwas",
  ADMIN: "greift ein",
  BLOCKED: "gesperrt",
};

interface Eigenschaften {
  aufruf: Werkzeugaufruf;
  aufFreigabe: (freigabeId: string, erlaubt: boolean) => void;
}

export function Werkzeugblock({ aufruf, aufFreigabe }: Eigenschaften) {
  const [ausgabeOffen, setAusgabeOffen] = useState(false);
  const wartet = aufruf.zustand === "wartet";
  const argumente = Object.entries(aufruf.args ?? {});

  return (
    <div className={"werkzeug ist-" + aufruf.zustand} data-stufe={aufruf.stufe}>
      <div className="werkzeug-kopf">
        <span className="werkzeug-zustand" aria-hidden="true">
          {aufruf.zustand === "laeuft" && <span className="puls" />}
          {aufruf.zustand === "wartet" && <Zeichen name="warnung" groesse={14} />}
          {aufruf.zustand === "fertig" && (
            <Zeichen name={aufruf.erfolg === false ? "kreuz" : "haken"} groesse={14} />
          )}
          {aufruf.zustand === "abgelehnt" && <Zeichen name="kreuz" groesse={14} />}
          {aufruf.zustand === "gesperrt" && <Zeichen name="kreuz" groesse={14} />}
        </span>

        <code className="werkzeug-name">{aufruf.name}</code>
        <span className="werkzeug-stufe">{STUFENTEXT[aufruf.stufe] ?? aufruf.stufe}</span>

        {aufruf.zustand === "fertig" && aufruf.ergebnis && (
          <button
            type="button"
            className="werkzeug-mehr"
            onClick={() => setAusgabeOffen((o) => !o)}
            aria-expanded={ausgabeOffen}
          >
            {ausgabeOffen ? "Ausgabe verbergen" : "Ausgabe zeigen"}
          </button>
        )}
      </div>

      {argumente.length > 0 && (
        <dl className="werkzeug-args">
          {argumente.map(([schluessel, wert]) => (
            <div key={schluessel}>
              <dt>{schluessel}</dt>
              <dd>
                <code>
                  {typeof wert === "string" ? wert : JSON.stringify(wert)}
                </code>
              </dd>
            </div>
          ))}
        </dl>
      )}

      {wartet && aufruf.freigabe_id && (
        <div className="werkzeug-frage">
          <p>
            {aufruf.stufe === "ADMIN"
              ? "Das greift auf einem echten System ein."
              : "Das verändert etwas."}{" "}
            Ausführen?
          </p>
          <div className="werkzeug-knoepfe">
            <button
              type="button"
              className="knopf-still"
              onClick={() => aufFreigabe(aufruf.freigabe_id!, false)}
            >
              Nein
            </button>
            <button
              type="button"
              className="knopf-betont"
              onClick={() => aufFreigabe(aufruf.freigabe_id!, true)}
              autoFocus
            >
              Ausführen
            </button>
          </div>
        </div>
      )}

      {aufruf.zustand === "abgelehnt" && (
        <p className="werkzeug-hinweis">Abgelehnt — nichts passiert.</p>
      )}
      {aufruf.zustand === "gesperrt" && (
        <p className="werkzeug-hinweis">
          Gesperrt. Dieser Befehl ist grundsätzlich nicht erlaubt.
        </p>
      )}

      {aufruf.ergebnis && (
        <div className={"werkzeug-klappe" + (ausgabeOffen ? " offen" : "")}>
          <div>
            <pre className="werkzeug-ausgabe roller">{aufruf.ergebnis}</pre>
          </div>
        </div>
      )}
    </div>
  );
}
