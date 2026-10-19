/** Agents, die gerade für das Modell arbeiten — eine Karte je Auftrag.
 *
 * Seit 2026-10-02 übernimmt kein Agent mehr das Gespräch: Das Modell gibt bis
 * zu vier Aufträge gleichzeitig ab und schreibt die Antwort selbst. Die
 * Karten zeigen, wer woran sitzt, was er gerade tut, und — aufklappbar — was
 * er dem Modell zurückgemeldet hat.
 *
 * Wartet ein Agent auf eine Freigabe, klappt seine Karte von selbst auf: Eine
 * Freigabe, die man erst suchen muss, wird übersehen.
 */

import { useEffect, useState } from "react";
import type { Auftrag } from "../daten/typen";
import { AgentZeichen } from "./Agents";
import { Antworttext } from "./Antworttext";
import { Werkzeugblock } from "./Werkzeugblock";
import { Zeichen } from "./Zeichen";
import "./AgentKarten.css";

function dauer(a: Auftrag, jetzt: number): string {
  const s = Math.max(0, Math.round(((a.ende ?? jetzt) - a.beginn) / 1000));
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`;
}

function Karte({ a, i, aufFreigabe }: { a: Auftrag; i: number; aufFreigabe: (id: string, erlaubt: boolean) => void }) {
  const wartet = a.schritte.some((w) => w.zustand === "wartet");
  const [offen, setOffen] = useState(false);
  const [jetzt, setJetzt] = useState(Date.now());
  useEffect(() => {
    if (a.zustand !== "laeuft") return;
    const t = setInterval(() => setJetzt(Date.now()), 1000);
    return () => clearInterval(t);
  }, [a.zustand]);
  const aufgeklappt = offen || wartet;
  const letzter = a.schritte[a.schritte.length - 1];
  const tut =
    a.zustand === "laeuft"
      ? wartet
        ? "wartet auf deine Freigabe"
        : letzter?.zustand === "laeuft"
          ? `${letzter.name} …`
          : a.status && a.status !== "thinking"
            ? a.status
            : "denkt nach"
      : a.zustand === "fertig"
        ? `${a.schritte.length} Schritt${a.schritte.length === 1 ? "" : "e"}`
        : "fehlgeschlagen";

  return (
    <article
      className={`agentkarte ist-${a.zustand}${wartet ? " wartet" : ""}${aufgeklappt ? " ist-offen" : ""}`}
      style={{ "--farbe": a.farbe ?? "var(--akzent)", "--i": i } as React.CSSProperties}
    >
      <button type="button" className="agentkarte-kopf" onClick={() => setOffen((o) => !o)} aria-expanded={aufgeklappt}>
        <AgentZeichen agent={{ name: a.name, color: a.farbe }} groesse={26} />
        <span className="agentkarte-titel">
          <strong>{a.name}</strong>
          <span className="agentkarte-tut">
            {a.zustand === "laeuft" && !wartet && <span className="agentkarte-puls" aria-hidden />}
            {a.zustand === "fertig" && <Zeichen name="haken" groesse={12} />}
            {a.zustand === "fehler" && <Zeichen name="kreuz" groesse={12} />}
            {wartet && <Zeichen name="warnung" groesse={12} />}
            {tut}
          </span>
        </span>
        <span className="agentkarte-zeit">{dauer(a, jetzt)}</span>
      </button>
      <p className="agentkarte-auftrag">{a.auftrag}</p>
      {a.zustand === "laeuft" && <span className="agentkarte-balken" aria-hidden />}
      {aufgeklappt && (
        <div className="agentkarte-inhalt">
          {a.schritte.length > 0 && (
            <div className="werkzeugliste">
              {a.schritte.map((w) => (
                <Werkzeugblock key={w.id} aufruf={w} aufFreigabe={aufFreigabe} />
              ))}
            </div>
          )}
          {a.zusammenfassung && (
            <div className="agentkarte-bericht">
              <span className="agentkarte-bericht-titel">Rückmeldung an Xera</span>
              <Antworttext text={a.zusammenfassung} />
            </div>
          )}
        </div>
      )}
    </article>
  );
}

interface Eigenschaften {
  auftraege: Auftrag[];
  aufFreigabe: (freigabeId: string, erlaubt: boolean) => void;
  /** Bei fertigen Antworten zusammengeklappt zu einer Zeile. */
  kompakt?: boolean;
}

export function AgentKarten({ auftraege, aufFreigabe, kompakt = false }: Eigenschaften) {
  const [ausgeklappt, setAusgeklappt] = useState(false);
  if (auftraege.length === 0) return null;
  const fertig = auftraege.filter((a) => a.zustand !== "laeuft").length;

  if (kompakt && !ausgeklappt) {
    return (
      <button type="button" className="agentkarten-zeile" onClick={() => setAusgeklappt(true)}>
        <span className="agentkarten-stapel">
          {auftraege.map((a) => (
            <AgentZeichen key={a.lauf} agent={{ name: a.name, color: a.farbe }} groesse={20} />
          ))}
        </span>
        {auftraege.length === 1 ? `${auftraege[0]!.name} hat mitgearbeitet` : `${auftraege.length} Agents haben mitgearbeitet`}
        <Zeichen name="pfeil-rechts" groesse={11} />
      </button>
    );
  }

  return (
    <section className="agentkarten" aria-label="Agents bei der Arbeit">
      {!kompakt && (
        <header className="agentkarten-kopf">
          <Zeichen name="agent" groesse={14} />
          {fertig < auftraege.length
            ? `${auftraege.length - fertig} von ${auftraege.length} Agent${auftraege.length === 1 ? "" : "s"} arbeiten gleichzeitig`
            : `${auftraege.length} Agent${auftraege.length === 1 ? "" : "s"} fertig — Xera schreibt die Antwort`}
        </header>
      )}
      <div className="agentkarten-raster" data-anzahl={auftraege.length}>
        {auftraege.map((a, i) => (
          <Karte key={a.lauf} a={a} i={i} aufFreigabe={aufFreigabe} />
        ))}
      </div>
    </section>
  );
}
