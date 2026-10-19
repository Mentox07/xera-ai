/** Wahl des Denkaufwands am Eingabefeld — ein kleines Menü über dem Knopf.
 *
 * Statt „Gründlich denken“ an/aus (bis 2026-10-19). Gleiche Stufen wie
 * `/effort` im Eingabefeld und die Varianten in der CLI.
 */

import { useEffect, useRef, useState } from "react";
import { STUFEN, aufwandName, type Aufwand } from "../daten/aufwand";
import { Zeichen } from "./Zeichen";
import "./AufwandWahl.css";

export function AufwandWahl({ wert, aufWahl }: { wert: Aufwand; aufWahl: (a: Aufwand) => void }) {
  const [offen, setOffen] = useState(false);
  const rahmenRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!offen) return;
    const weg = (e: MouseEvent) => {
      if (rahmenRef.current && !rahmenRef.current.contains(e.target as Node)) setOffen(false);
    };
    const taste = (e: KeyboardEvent) => e.key === "Escape" && setOffen(false);
    window.addEventListener("mousedown", weg);
    window.addEventListener("keydown", taste);
    return () => {
      window.removeEventListener("mousedown", weg);
      window.removeEventListener("keydown", taste);
    };
  }, [offen]);

  const an = wert !== "aus";
  return (
    <div className="aufwand" ref={rahmenRef}>
      <button
        type="button"
        className={"eingabe-werkzeug ist-denken" + (an ? " ist-an" : "")}
        onClick={() => setOffen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={offen}
        title={`Denkaufwand: ${aufwandName(wert)} — auch mit /effort im Eingabefeld`}
      >
        <Zeichen name="denken" groesse={16} />
        {an && <span className="aufwand-marke">{aufwandName(wert)}</span>}
      </button>
      {offen && (
        <div className="aufwand-menue" role="menu" aria-label="Denkaufwand">
          <div className="aufwand-titel">Denkaufwand</div>
          {STUFEN.map((s, i) => (
            <button
              key={s.id}
              type="button"
              role="menuitemradio"
              aria-checked={s.id === wert}
              className={"aufwand-stufe" + (s.id === wert ? " ist-gewaehlt" : "")}
              style={{ "--i": i } as React.CSSProperties}
              onClick={() => {
                aufWahl(s.id);
                setOffen(false);
              }}
            >
              <span className="aufwand-balken" aria-hidden="true">
                {[1, 2, 3, 4].map((b) => (
                  <i key={b} className={b <= i ? "ist-voll" : ""} />
                ))}
              </span>
              <span>
                <strong>{s.name}</strong>
                <small>{s.text}</small>
              </span>
            </button>
          ))}
          <div className="aufwand-fuss">
            Tipp: <code>/effort hoch</code> im Eingabefeld
          </div>
        </div>
      )}
    </div>
  );
}
