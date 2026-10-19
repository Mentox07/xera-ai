/** Die Befehlspalette (Strg K).
 *
 * Sie ist nicht Beiwerk, sondern der Hauptweg: Wer das Werkzeug täglich
 * benutzt, tippt schneller als er zielt. Alles, was einen Knopf hat, ist auch
 * hier zu finden — sonst zerfällt die Oberfläche in zwei Bedienarten, von
 * denen jede etwas kann, was die andere nicht kann.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { Zeichen, type ZeichenName } from "../bausteine/Zeichen";
import "./Palette.css";

export interface Befehl {
  id: string;
  name: string;
  /** Wonach noch gesucht wird, ohne dass es im Namen steht. */
  stichworte?: string;
  gruppe: string;
  zeichen?: ZeichenName;
  taste?: string;
  /** Erscheint ohne Suchbegriff nur in den ersten sechs — bei hundert
   *  Gesprächen wäre die Palette sonst eine endlose Liste. */
  nurBeiSuche?: boolean;
  ausfuehren: () => void;
}

interface Eigenschaften {
  offen: boolean;
  aufSchliessen: () => void;
  befehle: Befehl[];
}

export function Palette({ offen, aufSchliessen, befehle }: Eigenschaften) {
  const [suche, setSuche] = useState("");
  const [gewaehlt, setGewaehlt] = useState(0);
  const feldRef = useRef<HTMLInputElement>(null);
  const listeRef = useRef<HTMLUListElement>(null);

  // Beim Öffnen zurücksetzen: die alte Sucheingabe stehenzulassen ist der
  // sichere Weg, dass jemand den falschen Befehl auslöst.
  useEffect(() => {
    if (offen) {
      setSuche("");
      setGewaehlt(0);
      feldRef.current?.focus();
    }
  }, [offen]);

  const treffer = useMemo(() => {
    const s = suche.trim().toLowerCase();
    if (!s) {
      let gezeigt = 0;
      return befehle.filter((b) => !b.nurBeiSuche || gezeigt++ < 6);
    }
    return befehle.filter((b) =>
      (b.name + " " + (b.stichworte ?? "") + " " + b.gruppe).toLowerCase().includes(s),
    );
  }, [suche, befehle]);

  // Die Auswahl darf nicht hinter der Liste zurückbleiben, wenn getippt wird.
  useEffect(() => {
    setGewaehlt((g) => Math.min(g, Math.max(0, treffer.length - 1)));
  }, [treffer.length]);

  useEffect(() => {
    listeRef.current
      ?.querySelector<HTMLElement>('[data-gewaehlt="true"]')
      ?.scrollIntoView({ block: "nearest" });
  }, [gewaehlt]);

  if (!offen) return null;

  function tasten(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setGewaehlt((g) => (g + 1) % Math.max(1, treffer.length));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setGewaehlt((g) => (g - 1 + treffer.length) % Math.max(1, treffer.length));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const b = treffer[gewaehlt];
      if (b) {
        aufSchliessen();
        b.ausfuehren();
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      aufSchliessen();
    }
  }

  // Gruppen in der Reihenfolge ihres ersten Auftretens — nicht alphabetisch.
  // Die Reihenfolge in der Liste ist eine Aussage über Wichtigkeit.
  const gruppen: [string, Befehl[]][] = [];
  for (const b of treffer) {
    const vorhanden = gruppen.find(([g]) => g === b.gruppe);
    if (vorhanden) vorhanden[1].push(b);
    else gruppen.push([b.gruppe, [b]]);
  }

  let laufend = -1;

  return (
    <div className="palette-grund" onMouseDown={aufSchliessen} role="presentation">
      <div
        className="palette"
        onMouseDown={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Befehle"
      >
        <div className="palette-kopf">
          <Zeichen name="befehl" groesse={15} />
          <input
            ref={feldRef}
            className="palette-feld"
            value={suche}
            onChange={(e) => setSuche(e.target.value)}
            onKeyDown={tasten}
            placeholder="Befehl oder Gespräch suchen…"
            aria-label="Befehl suchen"
            autoComplete="off"
            spellCheck={false}
          />
          <kbd className="palette-esc">Esc</kbd>
        </div>

        {treffer.length === 0 ? (
          <p className="palette-leer">Nichts gefunden für „{suche}"</p>
        ) : (
          <ul className="palette-liste" ref={listeRef} role="listbox">
            {gruppen.map(([gruppe, eintraege]) => (
              <li key={gruppe}>
                <div className="palette-gruppe marke">{gruppe}</div>
                <ul>
                  {eintraege.map((b) => {
                    laufend += 1;
                    const ist = laufend === gewaehlt;
                    const meins = laufend;
                    return (
                      <li key={b.id}>
                        <button
                          type="button"
                          role="option"
                          aria-selected={ist}
                          data-gewaehlt={ist}
                          className={"palette-eintrag" + (ist ? " ist-gewaehlt" : "")}
                          style={{ "--i": meins } as React.CSSProperties}
                          onMouseEnter={() => setGewaehlt(meins)}
                          onClick={() => {
                            aufSchliessen();
                            b.ausfuehren();
                          }}
                        >
                          {b.zeichen && <Zeichen name={b.zeichen} groesse={15} />}
                          <span className="palette-name">{b.name}</span>
                          {b.taste && <kbd>{b.taste}</kbd>}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
