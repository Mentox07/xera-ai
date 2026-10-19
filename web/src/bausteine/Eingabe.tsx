/** Das Eingabefeld.
 *
 * Wächst mit dem Text, bis zu einer Grenze. Enter schickt, Umschalt+Enter
 * macht eine Zeile — die Reihenfolge ist bewusst so: In einem Chat ist
 * Abschicken der häufigere Fall, und wer das andersherum baut, zwingt bei
 * jeder Nachricht zu einem zweiten Griff.
 *
 * Anhänge kommen auf drei Wegen herein: Knopf, Einfügen (Strg V mit einem
 * Bild in der Zwischenablage) und Hineinziehen — Letzteres fängt die Fläche
 * darüber ab (Gespraechsbereich), weil man dort hinzielt, nicht auf das Feld.
 */

import { useEffect, useRef } from "react";
import { type Anhang, ERLAUBTE_DATEIEN } from "../daten/anhaenge";
import { Zeichen } from "./Zeichen";
import "./Eingabe.css";

interface Eigenschaften {
  wert: string;
  aufAenderung: (wert: string) => void;
  aufSenden: () => void;
  aufAbbruch: () => void;
  laeuft: boolean;
  platzhalter: string;
  /** Wird unter dem Feld angezeigt — etwa das gewählte Projekt. */
  hinweis?: React.ReactNode;
  gesperrt?: string;
  anhaenge?: Anhang[];
  aufDateien?: (dateien: File[]) => void;
  aufAnhangWeg?: (id: string) => void;
  /** Schalter links neben dem Feld (Websuche, Denken). */
  schalter?: React.ReactNode;
  /** Vor den Anhängen in der Chip-Zeile — etwa der gewählte Agent. */
  vorsatz?: React.ReactNode;
  /** Über dem Feld schwebend — etwa die @-Vorschläge. */
  ueber?: React.ReactNode;
  /** Bekommt jede Taste zuerst; `true` heißt „erledigt“. */
  aufTaste?: (e: React.KeyboardEvent<HTMLTextAreaElement>) => boolean;
}

const MAX_HOEHE = 220;

export function Eingabe({
  wert,
  aufAenderung,
  aufSenden,
  aufAbbruch,
  laeuft,
  platzhalter,
  hinweis,
  gesperrt,
  anhaenge = [],
  aufDateien,
  aufAnhangWeg,
  schalter,
  vorsatz,
  ueber,
  aufTaste,
}: Eigenschaften) {
  const feldRef = useRef<HTMLTextAreaElement>(null);
  const dateiRef = useRef<HTMLInputElement>(null);

  // Höhe an den Inhalt anpassen. Erst zurücksetzen, sonst wächst das Feld
  // nur und schrumpft beim Löschen nie wieder.
  useEffect(() => {
    const feld = feldRef.current;
    if (!feld) return;
    feld.style.height = "auto";
    feld.style.height = Math.min(feld.scrollHeight, MAX_HOEHE) + "px";
  }, [wert]);

  // Nach „Bearbeiten“ steht der Text wieder im Feld — dann soll der Cursor
  // auch gleich dort sein.
  useEffect(() => {
    if (!laeuft) feldRef.current?.focus();
  }, [laeuft]);

  const laedtNoch = anhaenge.some((a) => a.laedt);
  const sendbar = (wert.trim().length > 0 || anhaenge.some((a) => !a.fehler)) && !laedtNoch;

  function tasten(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (aufTaste?.(e)) return;
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      if (sendbar && !laeuft) aufSenden();
    }
  }

  function einfuegen(e: React.ClipboardEvent<HTMLTextAreaElement>) {
    if (!aufDateien) return;
    const bilder = Array.from(e.clipboardData.files).filter((d) => d.type.startsWith("image/"));
    if (bilder.length > 0) {
      e.preventDefault();
      aufDateien(bilder);
    }
  }

  if (gesperrt) {
    return (
      <div className="eingabe-bereich">
        <p className="eingabe-gesperrt">{gesperrt}</p>
      </div>
    );
  }

  return (
    <div className="eingabe-bereich">
      <div className={"eingabe" + (laeuft ? " laeuft" : "")}>
        {ueber}
        {(anhaenge.length > 0 || vorsatz) && (
          <ul className="anhaenge" aria-label="Anhänge">
            {vorsatz && <li className="anhang-vorsatz">{vorsatz}</li>}
            {anhaenge.map((a) => (
              <li
                key={a.id}
                className={"anhang" + (a.laedt ? " laedt" : "") + (a.fehler ? " fehlerhaft" : "")}
                title={a.fehler ?? a.name}
              >
                {a.art === "bild" && a.bild ? (
                  <img src={a.bild} alt="" />
                ) : (
                  <span className="anhang-zeichen">
                    <Zeichen name={a.fehler ? "warnung" : a.art === "bild" ? "anhang" : "notiz"} groesse={14} />
                  </span>
                )}
                {a.art === "dokument" && <span className="anhang-name">{a.name}</span>}
                {a.laedt && <span className="anhang-ring" aria-label="wird verarbeitet" />}
                {aufAnhangWeg && (
                  <button type="button" onClick={() => aufAnhangWeg(a.id)} aria-label={`${a.name} entfernen`}>
                    <Zeichen name="kreuz" groesse={10} />
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}

        <div className="eingabe-zeile">
          {aufDateien && (
            <>
              <button
                type="button"
                className="eingabe-werkzeug"
                onClick={() => dateiRef.current?.click()}
                title="Bild oder Dokument anhängen (auch: einfügen oder hineinziehen)"
                aria-label="Anhang hinzufügen"
              >
                <Zeichen name="anhang" groesse={16} />
              </button>
              <input
                ref={dateiRef}
                type="file"
                accept={ERLAUBTE_DATEIEN}
                multiple
                hidden
                onChange={(e) => {
                  const dateien = Array.from(e.target.files ?? []);
                  if (dateien.length) aufDateien(dateien);
                  e.target.value = "";
                }}
              />
            </>
          )}
          {schalter}
          <textarea
            ref={feldRef}
            className="eingabe-feld"
            value={wert}
            onChange={(e) => aufAenderung(e.target.value)}
            onKeyDown={tasten}
            onPaste={einfuegen}
            placeholder={platzhalter}
            rows={1}
            aria-label="Nachricht"
            spellCheck={false}
          />
          {laeuft ? (
            <button
              type="button"
              className="eingabe-knopf ist-stop"
              onClick={aufAbbruch}
              title="Abbrechen (Esc)"
              aria-label="Antwort abbrechen"
              key="stop"
            >
              <Zeichen name="stop" groesse={15} />
            </button>
          ) : (
            <button
              type="button"
              className="eingabe-knopf"
              onClick={aufSenden}
              disabled={!sendbar}
              title={laedtNoch ? "Anhänge werden noch verarbeitet" : "Senden (Enter)"}
              aria-label="Senden"
              key="senden"
            >
              <Zeichen name="senden" groesse={17} />
            </button>
          )}
        </div>
      </div>
      <div className="eingabe-fuss">
        {hinweis}
        <span className="eingabe-taste">
          <kbd>Enter</kbd> senden · <kbd>Umschalt+Enter</kbd> Zeile · <kbd>Strg V</kbd> Bild einfügen
        </span>
      </div>
    </div>
  );
}
