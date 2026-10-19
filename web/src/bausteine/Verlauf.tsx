/** Die Liste der Gespräche.
 *
 * Nach Zeit gruppiert, nicht als eine lange Liste: „Heute" und „Gestern" sagen
 * mehr als ein Datum an jeder Zeile, und die meisten Gespräche, die man sucht,
 * sind von heute.
 */

import { useMemo, useState } from "react";
import type { Sitzung } from "../daten/typen";
import { Zeichen } from "./Zeichen";
import "./Verlauf.css";

interface Eigenschaften {
  sitzungen: Sitzung[];
  aktiv: number | null;
  aufWaehlen: (id: number) => void;
  aufNeu: () => void;
  aufLoeschen: (id: number) => void;
  titel: string;
  /** Erste Ladung läuft noch: Platzhalter statt „Noch keine Gespräche“. */
  ladend?: boolean;
  /** Wird gerade entfernt — klappt animiert zu, bevor es aus der Liste fällt. */
  gehend?: number | null;
  /** In einen Ordner legen (oder herausnehmen, wenn schon in einem). */
  aufOrdner?: (sitzung: Sitzung) => void;
  /** Handy: Verlauf als Schublade. */
  offen?: boolean;
  aufSchliessen?: () => void;
}

/** Ordnet eine Sitzung einem Zeitraum zu. */
function zeitraum(sitzung: Sitzung): string {
  const roh = sitzung.updated_at ?? sitzung.created_at;
  if (!roh) return "Früher";
  const dann = new Date(roh);
  if (Number.isNaN(dann.getTime())) return "Früher";

  const heuteBeginn = new Date();
  heuteBeginn.setHours(0, 0, 0, 0);
  const tage = Math.floor((heuteBeginn.getTime() - dann.getTime()) / 86_400_000);

  if (tage < 0) return "Heute";
  if (tage === 0) return "Heute";
  if (tage === 1) return "Gestern";
  if (tage < 7) return "Diese Woche";
  if (tage < 30) return "Diesen Monat";
  return "Früher";
}

const REIHENFOLGE = ["Heute", "Gestern", "Diese Woche", "Diesen Monat", "Früher"];

export function Verlauf({
  sitzungen,
  aktiv,
  aufWaehlen,
  aufNeu,
  aufLoeschen,
  titel,
  ladend,
  gehend,
  aufOrdner,
  offen,
  aufSchliessen,
}: Eigenschaften) {
  const [suche, setSuche] = useState("");
  const [zu, setZu] = useState<Set<string>>(new Set());

  const gruppen = useMemo(() => {
    const s = suche.trim().toLowerCase();
    const gefiltert = s
      ? sitzungen.filter((x) => (x.title ?? "").toLowerCase().includes(s))
      : sitzungen;

    // Gespräche in Ordnern stehen oben, je Ordner eine Gruppe. Der Rest nach
    // Zeit. Ein Ordner ist eine Entscheidung, die jemand getroffen hat — die
    // wiegt mehr als das Datum.
    const ordner = new Map<string, Sitzung[]>();
    const lose: Sitzung[] = [];
    for (const sitzung of gefiltert) {
      if (sitzung.folder) {
        const l = ordner.get(sitzung.folder);
        if (l) l.push(sitzung);
        else ordner.set(sitzung.folder, [sitzung]);
      } else lose.push(sitzung);
    }

    const karte = new Map<string, Sitzung[]>();
    for (const sitzung of lose) {
      const raum = zeitraum(sitzung);
      const liste = karte.get(raum);
      if (liste) liste.push(sitzung);
      else karte.set(raum, [sitzung]);
    }
    const ordnerGruppen = [...ordner.keys()]
      .sort((a, b) => a.localeCompare(b, "de"))
      .map((o) => ["ordner:" + o, ordner.get(o)!] as const);
    return [
      ...ordnerGruppen,
      ...REIHENFOLGE.filter((r) => karte.has(r)).map((r) => [r, karte.get(r)!] as const),
    ];
  }, [sitzungen, suche]);

  return (
    <>
    {offen && <div className="verlauf-grund" onClick={aufSchliessen} aria-hidden="true" />}
    <aside className={"verlauf" + (offen ? " offen" : "")} aria-label={titel}>
      <div className="verlauf-kopf">
        <span className="marke">{titel}</span>
        <button type="button" onClick={aufNeu} title="Neues Gespräch (Strg N)" aria-label="Neues Gespräch">
          <Zeichen name="neu" groesse={15} />
        </button>
      </div>

      {sitzungen.length > 4 && (
        <input
          className="verlauf-suche"
          value={suche}
          onChange={(e) => setSuche(e.target.value)}
          placeholder="Filtern…"
          aria-label="Gespräche filtern"
          spellCheck={false}
        />
      )}

      <div className="verlauf-liste">
        {ladend && sitzungen.length === 0 ? (
          <div aria-label="Wird geladen">
            {[72, 56, 84, 48, 66, 60].map((breite, i) => (
              <span key={i} className="skelett" style={{ width: `${breite}%`, animationDelay: `${i * 90}ms` }} />
            ))}
          </div>
        ) : gruppen.length === 0 ? (
          <p className="verlauf-leer">
            {suche ? "Nichts gefunden." : "Noch keine Gespräche."}
          </p>
        ) : (
          gruppen.map(([raum, eintraege]) => {
            const istOrdner = raum.startsWith("ordner:");
            const zugeklappt = istOrdner && zu.has(raum);
            return (
            <section key={raum} className={istOrdner ? "verlauf-ordner" + (zugeklappt ? " zu" : "") : undefined}>
              {istOrdner ? (
                <button
                  type="button"
                  className="marke verlauf-raum verlauf-ordner-kopf"
                  aria-expanded={!zugeklappt}
                  onClick={() =>
                    setZu((alt) => {
                      const neu = new Set(alt);
                      if (neu.has(raum)) neu.delete(raum);
                      else neu.add(raum);
                      return neu;
                    })
                  }
                >
                  <Zeichen name="pfeil-rechts" groesse={11} />
                  <Zeichen name="ordner" groesse={13} />
                  <span>{raum.slice(7)}</span>
                  <small>{eintraege.length}</small>
                </button>
              ) : (
                <h3 className="marke verlauf-raum">{raum}</h3>
              )}
              <ul>
                {eintraege.map((s) => (
                  <li key={s.id} className={gehend === s.id ? "geht" : undefined}>
                    <button
                      type="button"
                      style={{ "--i": sitzungen.indexOf(s) } as React.CSSProperties}
                      className={"verlauf-eintrag" + (aktiv === s.id ? " ist-aktiv" : "")}
                      onClick={() => aufWaehlen(s.id)}
                      aria-current={aktiv === s.id ? "true" : undefined}
                    >
                      <span className="verlauf-titel">{s.title || "Ohne Titel"}</span>
                    </button>
                    {aufOrdner && (
                      <button
                        type="button"
                        className="verlauf-weg verlauf-ordnen"
                        onClick={() => aufOrdner(s)}
                        title={s.folder ? `Aus „${s.folder}“ nehmen` : "In einen Ordner legen"}
                        aria-label={s.folder ? "Aus dem Ordner nehmen" : "In einen Ordner legen"}
                      >
                        <Zeichen name="ordner" groesse={13} />
                      </button>
                    )}
                    <button
                      type="button"
                      className="verlauf-weg"
                      onClick={() => aufLoeschen(s.id)}
                      title="Löschen"
                      aria-label={`Gespräch „${s.title || "Ohne Titel"}" löschen`}
                    >
                      <Zeichen name="muell" groesse={13} />
                    </button>
                  </li>
                ))}
              </ul>
            </section>
            );
          })
        )}
      </div>
    </aside>
    </>
  );
}
