/** Die Fläche, auf der ein Gespräch steht.
 *
 * Alle vier Bereiche benutzen sie — was sie unterscheidet, ist der Modus, die
 * Werkzeuge und der Begrüssungstext, nicht die Darstellung. Vier Fassungen
 * desselben Verlaufs zu pflegen war einer der Gründe, warum das alte Frontend
 * auf 4 145 Zeilen kam.
 */

import { useEffect, useRef, useState } from "react";
import type { Auftrag, Nachricht, Werkzeugaufruf } from "../daten/typen";
import { AgentKarten } from "./AgentKarten";
import { dokumentName } from "../daten/useGespraech";
import { Antworttext } from "./Antworttext";
import { Gedankengang } from "./Gedankengang";
import { Werkzeugblock } from "./Werkzeugblock";
import { Zeichen } from "./Zeichen";
import "./Gespraechsflaeche.css";

interface Eigenschaften {
  nachrichten: Nachricht[];
  laufend: string;
  werkzeuge: Werkzeugaufruf[];
  /** Agent-Aufträge der laufenden Antwort. */
  auftraege?: Auftrag[];
  agent: { id: string; name: string } | null;
  status: string | null;
  /** Verbindung weg, es wird neu verbunden. */
  getrennt?: boolean;
  laeuft: boolean;
  fehler: string | null;
  aufFreigabe: (freigabeId: string, erlaubt: boolean) => void;
  /** Steht da, solange nichts geschrieben wurde. */
  begruessung: React.ReactNode;
  aufNeuErzeugen?: () => void;
  aufBearbeiten?: (index: number) => void;
  /** Denkweg der laufenden Antwort. */
  gedanken?: string;
  denkBeginn?: number | null;
  /** „Jetzt antworten“: Xera beendet das Nachdenken (seit 2026-10-19). */
  aufJetztAntworten?: () => void;
}

/** Nach der Antwort: benutzte Werkzeuge als eine Zeile, aufklappbar. */
function WerkzeugZeile({ werkzeuge, aufFreigabe }: { werkzeuge: Werkzeugaufruf[]; aufFreigabe: (id: string, erlaubt: boolean) => void }) {
  const [offen, setOffen] = useState(false);
  const namen = [...new Set(werkzeuge.map((w) => w.name))].join(", ");
  return (
    <div className="werkzeug-zeile">
      <button type="button" className="agentkarten-zeile" onClick={() => setOffen((o) => !o)} aria-expanded={offen}>
        <Zeichen name="befehl" groesse={13} />
        {werkzeuge.length} Werkzeug{werkzeuge.length === 1 ? "" : "e"} benutzt · {namen}
        <Zeichen name="pfeil-rechts" groesse={11} />
      </button>
      {offen && (
        <div className="werkzeugliste">
          {werkzeuge.map((w) => (
            <Werkzeugblock key={w.id} aufruf={w} aufFreigabe={aufFreigabe} />
          ))}
        </div>
      )}
    </div>
  );
}

/** Kopieren mit Rückmeldung am Knopf selbst — eine Meldung unten rechts wäre
 *  für so etwas Kleines zu laut. */
function KopierKnopf({ text }: { text: string }) {
  const [kopiert, setKopiert] = useState(false);
  return (
    <button
      type="button"
      className={kopiert ? "ist-kopiert" : undefined}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setKopiert(true);
          setTimeout(() => setKopiert(false), 1400);
        } catch {
          /* Ohne HTTPS keine Zwischenablage — der Text lässt sich markieren. */
        }
      }}
      title="Kopieren"
      aria-label="Nachricht kopieren"
    >
      <Zeichen name={kopiert ? "haken" : "kopieren"} groesse={14} />
      <span>{kopiert ? "kopiert" : "Kopieren"}</span>
    </button>
  );
}

export function Gespraechsflaeche({
  nachrichten,
  laufend,
  werkzeuge,
  auftraege = [],
  agent,
  status,
  laeuft,
  getrennt = false,
  fehler,
  aufFreigabe,
  begruessung,
  aufNeuErzeugen,
  aufBearbeiten,
  gedanken = "",
  denkBeginn,
  aufJetztAntworten,
}: Eigenschaften) {
  const letzteAntwort = nachrichten.map((n) => n.role).lastIndexOf("assistant");
  const endeRef = useRef<HTMLDivElement>(null);
  const flaecheRef = useRef<HTMLDivElement>(null);
  // Ob der Blick unten klebt. Wer hochgescrollt hat, um etwas nachzulesen,
  // will nicht bei jedem Zeichen wieder nach unten gerissen werden.
  const klebtRef = useRef(true);

  useEffect(() => {
    const flaeche = flaecheRef.current;
    if (!flaeche) return;
    function pruefen() {
      const abstand = flaeche!.scrollHeight - flaeche!.scrollTop - flaeche!.clientHeight;
      klebtRef.current = abstand < 90;
    }
    flaeche.addEventListener("scroll", pruefen, { passive: true });
    return () => flaeche.removeEventListener("scroll", pruefen);
  }, []);

  useEffect(() => {
    if (klebtRef.current) {
      endeRef.current?.scrollIntoView({ block: "end" });
    }
  }, [nachrichten.length, laufend, werkzeuge.length, auftraege.length, status]);

  const leer = nachrichten.length === 0 && !laufend && werkzeuge.length === 0;

  return (
    <div className="gespraech" ref={flaecheRef}>
      {leer ? (
        <div className="gespraech-leer">{begruessung}</div>
      ) : (
        <div className="gespraech-lauf">
          {nachrichten.map((n, i) =>
            n.role === "user" ? (
              <div
                className="nachricht ist-frage"
                key={n.id ?? i}
                style={{ "--i": i } as React.CSSProperties}
              >
                {(n.bilder?.length || n.dokumente?.length) ? (
                  <div className="frage-anhaenge">
                    {n.bilder?.map((b, j) => (
                      <img key={j} src={b} alt="Angehängtes Bild" />
                    ))}
                    {n.dokumente?.map((d) => (
                      <span key={d} className="frage-dokument">
                        <Zeichen name="notiz" groesse={13} />
                        {dokumentName(d)}
                      </span>
                    ))}
                  </div>
                ) : null}
                <div className="frage-text">{n.content}</div>
                {!laeuft && (
                  <div className="aktionen">
                    <KopierKnopf text={n.content} />
                    {aufBearbeiten && (
                      <button type="button" onClick={() => aufBearbeiten(i)} title="Frage bearbeiten">
                        <Zeichen name="stift" groesse={14} />
                        <span>Bearbeiten</span>
                      </button>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <div
                className={"nachricht ist-antwort" + (n.still ? " ohne-auftritt" : "")}
                key={n.id ?? i}
                style={{ "--i": i } as React.CSSProperties}
              >
                {n.gedanken && <Gedankengang text={n.gedanken} sekunden={n.denkSekunden} />}
                {n.werkzeuge && <WerkzeugZeile werkzeuge={n.werkzeuge} aufFreigabe={aufFreigabe} />}
                {n.auftraege && <AgentKarten auftraege={n.auftraege} aufFreigabe={aufFreigabe} kompakt />}
                <Antworttext text={n.content} />
                {!laeuft && (
                  <div className="aktionen">
                    <KopierKnopf text={n.content} />
                    {aufNeuErzeugen && i === letzteAntwort && (
                      <button type="button" onClick={aufNeuErzeugen} title="Antwort neu erzeugen">
                        <Zeichen name="nochmal" groesse={14} />
                        <span>Neu erzeugen</span>
                      </button>
                    )}
                  </div>
                )}
              </div>
            ),
          )}

          {(laeuft || laufend || werkzeuge.length > 0 || auftraege.length > 0 || status || agent) && (
            <div className="nachricht ist-antwort">
              {agent && (
                <div className="agent-marke">
                  <Zeichen name="pfeil-rechts" groesse={12} />
                  {agent.name}
                </div>
              )}

              {werkzeuge.length > 0 && (
                <div className="werkzeugliste">
                  {werkzeuge.map((w) => (
                    <Werkzeugblock key={w.id} aufruf={w} aufFreigabe={aufFreigabe} />
                  ))}
                </div>
              )}

              <AgentKarten auftraege={auftraege} aufFreigabe={aufFreigabe} />

              {gedanken && !laufend && <Gedankengang text={gedanken} live beginn={denkBeginn} aufJetztAntworten={aufJetztAntworten} />}
              {gedanken && laufend && <Gedankengang text={gedanken} beginn={denkBeginn} sekunden={denkBeginn ? Math.round((Date.now() - denkBeginn) / 1000) : undefined} />}

              {laufend && <Antworttext text={laufend} laeuft={laeuft} />}

              {/* Auch ohne Status-Ereignis vom Backend: Zwischen Absenden und
                  erstem Wort darf die Fläche nicht leer stehen — sonst wirkt
                  es, als sei nichts passiert. */}
              {getrennt && (
                <p className="status denkt">
                  <span className="denkt-kugel" aria-hidden="true" />
                  <span className="denkt-wort">Verbindung unterbrochen — verbinde neu …</span>
                </p>
              )}

              {!getrennt && (status || (laeuft && werkzeuge.every((w) => w.zustand !== "laeuft") && auftraege.every((a) => a.zustand !== "laeuft"))) && !laufend && !gedanken && (
                <p className="status denkt">
                  <span className="denkt-kugel" aria-hidden="true" />
                  <span className="denkt-wort">
                    {!status || status === "thinking" ? "denkt nach" : status}
                  </span>
                </p>
              )}

              {laeuft && laufend && <span className="strich" aria-hidden="true" />}
            </div>
          )}

          {fehler && (
            <div className="gespraech-fehler" role="alert">
              <Zeichen name="warnung" groesse={15} />
              <span>{fehler}</span>
            </div>
          )}
        </div>
      )}
      <div ref={endeRef} />
    </div>
  );
}
