/** Die Vorführung auf der Seite „CLI“: ein Terminal mit OpenCode und Xera.
 *
 * Wie die Vorführung der Startseite (Vorfuehrung.tsx), nur im Terminal: Der
 * Befehl wird getippt, die Frage erscheint, Werkzeuge laufen auf dem eigenen
 * Rechner, die Antwort baut sich auf. Aufgebaut wie OpenCode selbst — Frage
 * mit Balken links, Werkzeugzeilen, darunter Modus und Modell —, aber
 * vereinfacht, kein Bildschirmfoto.
 *
 * Alles steht von Anfang an im Aufbau und wird nur sichtbar geschaltet: So
 * springt die Höhe nicht, während getippt wird. Wer „Bewegung reduzieren“
 * eingestellt hat, sieht gleich den fertigen Zustand.
 */

import { useEffect, useState } from "react";
import { SYSTEM } from "../daten/system";
import { bewegungAus } from "../stil/bewegung";
import "./Terminal.css";

const ORDNER = "~/fotos";
const BEFEHL = "opencode";
const FRAGE = "Schreib ein Skript, das alle Fotos hier auf 1600 px verkleinert.";
const WERKZEUGE: { zeichen: string; name: string; ziel: string; ausgabe?: string }[] = [
  { zeichen: "←", name: "Write", ziel: "verkleinern.py" },
  { zeichen: "$", name: "Shell", ziel: "python3 verkleinern.py --probe", ausgabe: "12 Bilder gefunden, Probe ok" },
];
const ANTWORT =
  "Fertig: verkleinern.py verkleinert alle JPG und PNG auf höchstens 1600 px und legt sie in klein/ ab. Starten mit python3 verkleinern.py.";

type Schritt = "befehl" | "frage" | "werkzeug" | "antwort" | "steht";

/** Getippter Teil sichtbar, der Rest unsichtbar dahinter — die Zeile bricht
 *  schon beim ersten Buchstaben so um wie am Ende. */
function Getippt({ text, bis, cursor }: { text: string; bis: number; cursor: boolean }) {
  return (
    <>
      {text.slice(0, bis)}
      {cursor && <span className="term-cursor" />}
      <span className="term-rest">{text.slice(bis)}</span>
    </>
  );
}

export function Terminal() {
  const ruhig = bewegungAus();
  const [schritt, setSchritt] = useState<Schritt>(ruhig ? "steht" : "befehl");
  const [befehl, setBefehl] = useState(ruhig ? BEFEHL.length : 0);
  const [frage, setFrage] = useState(ruhig ? FRAGE.length : 0);
  // je Werkzeug: 0 = noch nicht, 1 = läuft, 2 = fertig
  const [werkzeuge, setWerkzeuge] = useState<number[]>(WERKZEUGE.map(() => (ruhig ? 2 : 0)));
  const [antwort, setAntwort] = useState(ruhig ? ANTWORT.length : 0);

  useEffect(() => {
    if (ruhig) return;
    let t: ReturnType<typeof setTimeout>;
    if (schritt === "befehl") {
      if (befehl < BEFEHL.length) t = setTimeout(() => setBefehl((n) => n + 1), 90 + Math.random() * 60);
      else t = setTimeout(() => setSchritt("frage"), 700);
    } else if (schritt === "frage") {
      if (frage < FRAGE.length) t = setTimeout(() => setFrage((n) => n + 1), 30 + Math.random() * 35);
      else t = setTimeout(() => setSchritt("werkzeug"), 600);
    } else if (schritt === "werkzeug") {
      const i = werkzeuge.findIndex((w) => w < 2);
      if (i === -1) t = setTimeout(() => setSchritt("antwort"), 400);
      else
        t = setTimeout(
          () => setWerkzeuge((alt) => alt.map((w, j) => (j === i ? w + 1 : w))),
          werkzeuge[i] === 0 ? 250 : 1300,
        );
    } else if (schritt === "antwort") {
      if (antwort < ANTWORT.length) t = setTimeout(() => setAntwort((n) => Math.min(ANTWORT.length, n + 3)), 30);
      else t = setTimeout(() => setSchritt("steht"), 250);
    } else {
      // Stehen lassen, dann von vorn.
      t = setTimeout(() => {
        setBefehl(0);
        setFrage(0);
        setWerkzeuge(WERKZEUGE.map(() => 0));
        setAntwort(0);
        setSchritt("befehl");
      }, 6000);
    }
    return () => clearTimeout(t);
  }, [ruhig, schritt, befehl, frage, werkzeuge, antwort]);

  const imProgramm = schritt !== "befehl";

  return (
    <div className="term" aria-hidden="true">
      <div className="term-kopf">
        <span className="term-punkte">
          <span />
          <span />
          <span />
        </span>
        <span className="term-titel">
          {ORDNER} — {imProgramm ? "opencode" : "bash"}
        </span>
      </div>

      <div className="term-inhalt">
        <p className="term-zeile">
          <span className="term-prompt">{ORDNER} $</span>{" "}
          <Getippt text={BEFEHL} bis={befehl} cursor={schritt === "befehl"} />
        </p>

        <div className={"term-tui" + (imProgramm ? " ist-an" : "")}>
          <p className="term-frage">
            <Getippt text={FRAGE} bis={frage} cursor={schritt === "frage"} />
          </p>

          {WERKZEUGE.map((w, i) => (
            <div key={w.name} className={"term-werkzeug" + (werkzeuge[i]! > 0 ? " ist-an" : "")}>
              <p>
                <span className={"term-status" + (werkzeuge[i] === 2 ? " ist-fertig" : "")}>
                  {werkzeuge[i] === 2 ? "✓" : w.zeichen}
                </span>
                <span className="term-wname">{w.name}</span>
                <span className="term-ziel">{w.ziel}</span>
              </p>
              {w.ausgabe && (
                <p className={"term-ausgabe" + (werkzeuge[i] === 2 ? " ist-an" : "")}>{w.ausgabe}</p>
              )}
            </div>
          ))}

          <p className="term-antwort">
            <Getippt text={ANTWORT} bis={antwort} cursor={schritt === "antwort"} />
          </p>

          <p className={"term-fuss" + (schritt === "steht" ? " ist-an" : "")}>
            <span className="term-modus">Build</span> · Xera ({SYSTEM.modell}) · 38s
          </p>
        </div>
      </div>
    </div>
  );
}
