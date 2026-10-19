/** Der Denkweg des Modells (Denkmodus).
 *
 * Während es denkt: ein Fenster, in dem die Gedanken live durchlaufen, oben
 * ausgeblendet, unten das Neueste — man sieht, dass etwas passiert und
 * ungefähr was, ohne dass es die Antwort verdrängt. Danach: eine Zeile
 * „Nachgedacht · 23 s“, die sich aufklappen lässt.
 */

import { useEffect, useRef, useState } from "react";
import { Zeichen } from "./Zeichen";
import "./Gedankengang.css";

interface Eigenschaften {
  text: string;
  /** Denkt noch (live). */
  live?: boolean;
  beginn?: number | null;
  sekunden?: number;
  /** „Jetzt antworten“: Xera beendet das Nachdenken und schreibt die Antwort. */
  aufJetztAntworten?: () => void;
}

export function Gedankengang({ text, live, beginn, sekunden, aufJetztAntworten }: Eigenschaften) {
  const [offen, setOffen] = useState(false);
  const [gedrueckt, setGedrueckt] = useState(false);
  const [jetzt, setJetzt] = useState(Date.now());
  const fensterRef = useRef<HTMLDivElement>(null);

  // Uhr während des Denkens.
  useEffect(() => {
    if (!live) return;
    const t = setInterval(() => setJetzt(Date.now()), 500);
    return () => clearInterval(t);
  }, [live]);

  // Immer das Neueste zeigen.
  useEffect(() => {
    if (live && fensterRef.current) fensterRef.current.scrollTop = fensterRef.current.scrollHeight;
  }, [text, live]);

  const dauer = live && beginn ? Math.max(0, Math.round((jetzt - beginn) / 1000)) : (sekunden ?? 0);

  if (live) {
    return (
      <div className="gedanken ist-live">
        <div className="gedanken-kopf">
          <span className="denkt-kugel" aria-hidden="true" />
          <span className="denkt-wort">{gedrueckt ? "hört auf zu denken …" : "denkt nach"}</span>
          <span className="gedanken-zeit zahlen">{dauer} s</span>
          {aufJetztAntworten && (
            <button
              type="button"
              className="gedanken-jetzt"
              disabled={gedrueckt}
              onClick={() => {
                setGedrueckt(true);
                aufJetztAntworten();
              }}
              title="Nachdenken beenden — Xera schreibt sofort die Antwort"
            >
              Jetzt antworten
            </button>
          )}
        </div>
        <div className="gedanken-fenster" ref={fensterRef} aria-live="off">
          {text}
        </div>
      </div>
    );
  }

  return (
    <div className={"gedanken" + (offen ? " offen" : "")}>
      <button type="button" className="gedanken-schalter" onClick={() => setOffen((o) => !o)} aria-expanded={offen}>
        <Zeichen name="denken" groesse={14} />
        <span>Nachgedacht{dauer ? ` · ${dauer} s` : ""}</span>
        <Zeichen name="pfeil-rechts" groesse={12} />
      </button>
      <div className="gedanken-klappe">
        <div>
          <div className="gedanken-text">{text}</div>
        </div>
      </div>
    </div>
  );
}
