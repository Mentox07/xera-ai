/** Meldungen und Rückfragen.
 *
 * Ersetzt `alert()` und `prompt()`. Die sehen in jedem Browser anders aus,
 * halten die ganze Seite an und lassen sich nicht gestalten — und vor allem
 * gab es bis Oktober 2026 an vielen Stellen gar keine Meldung: Ein Fehler
 * beim Löschen oder Speichern verschwand still in einem leeren `catch`.
 *
 * Zwei Wege:
 * * `melden(text, art)` — eine Meldung unten rechts, die von selbst geht.
 * * `fragen({...})` — ein Dialog, der auf eine Antwort wartet (Promise).
 */

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { Zeichen, type ZeichenName } from "./Zeichen";
import "./Rueckmeldung.css";

type Art = "info" | "gut" | "fehler";

interface Meldung {
  id: number;
  text: string;
  art: Art;
  geht: boolean;
}

export interface Rueckfrage {
  titel: string;
  text?: string;
  /** Mit Eingabefeld: Die Antwort ist der eingegebene Text. */
  eingabe?: { platzhalter?: string; wert?: string };
  bestaetigen?: string;
  abbrechen?: string;
  /** Rot statt Akzent — für Löschen und Ähnliches. */
  gefaehrlich?: boolean;
}

interface Kontext {
  melden: (text: string, art?: Art) => void;
  /** `null` bei Abbruch, `true` oder der eingegebene Text bei Bestätigung. */
  fragen: (frage: Rueckfrage) => Promise<string | true | null>;
}

const RueckmeldungsKontext = createContext<Kontext | null>(null);

export function useRueckmeldung(): Kontext {
  const k = useContext(RueckmeldungsKontext);
  if (!k) throw new Error("useRueckmeldung außerhalb von <RueckmeldungsAnbieter>");
  return k;
}

const ZEICHEN: Record<Art, ZeichenName> = { info: "notiz", gut: "haken", fehler: "warnung" };
const DAUER_MS = 4200;

export function RueckmeldungsAnbieter({ children }: { children: React.ReactNode }) {
  const [meldungen, setMeldungen] = useState<Meldung[]>([]);
  const [frage, setFrage] = useState<(Rueckfrage & { antwort: (w: string | true | null) => void }) | null>(null);
  const zaehler = useRef(0);

  const weg = useCallback((id: number) => {
    // Erst als „geht“ markieren, damit die Ausblende-Animation laufen kann.
    setMeldungen((m) => m.map((x) => (x.id === id ? { ...x, geht: true } : x)));
    setTimeout(() => setMeldungen((m) => m.filter((x) => x.id !== id)), 320);
  }, []);

  const melden = useCallback(
    (text: string, art: Art = "info") => {
      const id = ++zaehler.current;
      setMeldungen((m) => [...m.slice(-3), { id, text, art, geht: false }]);
      setTimeout(() => weg(id), art === "fehler" ? DAUER_MS * 1.6 : DAUER_MS);
    },
    [weg],
  );

  const fragen = useCallback(
    (f: Rueckfrage) => new Promise<string | true | null>((antwort) => setFrage({ ...f, antwort })),
    [],
  );

  return (
    <RueckmeldungsKontext.Provider value={{ melden, fragen }}>
      {children}

      <div className="meldungen" aria-live="polite">
        {meldungen.map((m) => (
          <div
            key={m.id}
            className={`meldung ist-${m.art}${m.geht ? " geht" : ""}`}
            role={m.art === "fehler" ? "alert" : "status"}
            style={{ "--meldung-dauer": `${m.art === "fehler" ? DAUER_MS * 1.6 : DAUER_MS}ms` } as React.CSSProperties}
          >
            <Zeichen name={ZEICHEN[m.art]} groesse={15} />
            <span>{m.text}</span>
            <button type="button" onClick={() => weg(m.id)} aria-label="Meldung schließen">
              <Zeichen name="kreuz" groesse={12} />
            </button>
            <i className="meldung-zeit" aria-hidden="true" />
          </div>
        ))}
      </div>

      {frage && (
        <Dialog
          frage={frage}
          aufAntwort={(w) => {
            frage.antwort(w);
            setFrage(null);
          }}
        />
      )}
    </RueckmeldungsKontext.Provider>
  );
}

function Dialog({
  frage,
  aufAntwort,
}: {
  frage: Rueckfrage;
  aufAntwort: (w: string | true | null) => void;
}) {
  const [wert, setWert] = useState(frage.eingabe?.wert ?? "");
  const [geht, setGeht] = useState(false);
  const feldRef = useRef<HTMLInputElement>(null);
  const knopfRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    (feldRef.current ?? knopfRef.current)?.focus();
    feldRef.current?.select();
  }, []);

  function schliessen(w: string | true | null) {
    setGeht(true);
    setTimeout(() => aufAntwort(w), 200);
  }

  const ok = () => {
    if (frage.eingabe) {
      const t = wert.trim();
      if (!t) return;
      schliessen(t);
    } else schliessen(true);
  };

  return (
    <div
      className={"dialog-grund" + (geht ? " geht" : "")}
      onMouseDown={(e) => e.target === e.currentTarget && schliessen(null)}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.preventDefault();
          schliessen(null);
        }
      }}
    >
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="dialog-titel">
        <h2 id="dialog-titel">{frage.titel}</h2>
        {frage.text && <p className="dialog-text">{frage.text}</p>}
        {frage.eingabe && (
          <input
            ref={feldRef}
            className="dialog-feld"
            value={wert}
            placeholder={frage.eingabe.platzhalter}
            onChange={(e) => setWert(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ok()}
            spellCheck={false}
          />
        )}
        <div className="dialog-knoepfe">
          <button type="button" className="knopf-still" onClick={() => schliessen(null)}>
            {frage.abbrechen ?? "Abbrechen"}
          </button>
          <button
            ref={knopfRef}
            type="button"
            className={frage.gefaehrlich ? "knopf-gefahr" : "knopf-betont"}
            onClick={ok}
            disabled={Boolean(frage.eingabe) && !wert.trim()}
          >
            {frage.bestaetigen ?? "OK"}
          </button>
        </div>
      </div>
    </div>
  );
}
