/** Über uns.
 *
 * Wer es baut, was es ist, was es nicht ist. Die Grenzen stehen hier und
 * nicht auf der Startseite: Dort wären sie eine Warnung an Leute, die noch
 * gar nicht wissen, worum es geht. Hier sind sie eine Auskunft an die, die
 * schon interessiert sind.
 */

import { SYSTEM, zahl } from "../daten/system";
import "./Start.css";

const GRENZEN = [
  [
    "Es ist langsamer als große Anbieter",
    `Rund ${SYSTEM.schreibenTs} Token je Sekunde. Eine lange Antwort dauert eine halbe Minute, eine Aufgabe, bei der Agents Dateien bauen und testen, mehrere Minuten.`,
  ],
  [
    "Es weiß weniger",
    "Ein Modell dieser Größe auf dieser Hardware kann nicht, was ein Rechenzentrum kann. Bei Randwissen liegt es öfter daneben.",
  ],
  [
    "Lange Texte brauchen Anlauf",
    `Bis zu ${zahl(SYSTEM.kontext)} Token passen hinein, aber das Einlesen kostet Zeit: Ein volles Fenster braucht rund ${SYSTEM.vollesFensterMin} Minuten, bevor das erste Wort kommt. Folgefragen gehen danach in Sekunden, solange das Gelesene im Zwischenspeicher liegt.`,
  ],
  ["Es kann ausfallen", "Ein Server, ein Standort, kein Ersatzgerät. Und je Bereich rechnet es eine Anfrage nach der anderen — wer gleichzeitig im selben Bereich fragt, wartet."],
];

export function UeberUns() {
  return (
    <main className="seite">
      <section className="aufschlag">
        <h1>Über uns</h1>
        <p className="aufschlag-satz">
          Zwei Leute aus der Schweiz, ein gebrauchter Server, ein offenes
          Sprachmodell.
        </p>
      </section>

      <section className="abschnitt">
        <h2>Wer</h2>
        <div className="raster">
          <article>
            <h3>Miguel</h3>
            <p className="rolle">Informatiker EFZ Plattformentwicklung, im Lehrbetrieb</p>
            <p>
              Baut und betreibt die Infrastruktur: Server, Netz, Modell,
              Anwendung.
            </p>
          </article>
          <article>
            <h3>Sascha</h3>
            <p className="rolle">Gymnasium, Abschluss 2026</p>
            <p>Mitentwicklung.</p>
          </article>
        </div>
      </section>

      <section className="abschnitt">
        <h2>Warum</h2>
        <div className="text fliesstext">
          <p>
            Xera ist als Lernprojekt entstanden. Ein Sprachmodell selbst
            aufzusetzen zwingt dazu, alles zu verstehen, was sonst hinter einer
            Schnittstelle verschwindet: wie ein Modell in den Speicher passt,
            warum es unterschiedlich schnell liest und schreibt, was ein
            Kontextfenster begrenzt.
          </p>
          <p>
            Weil das Modell hier steht, lässt sich damit herumprobieren, ohne
            dass es etwas kostet. Deshalb gibt es die Seite{" "}
            <em>How Xera works</em> — sie erklärt mit Bildern, was dabei
            passiert. Sie ist für Schülerinnen und Schüler gedacht, aber es
            braucht kein Vorwissen.
          </p>
          <p>
            Der Quelltext liegt offen auf{" "}
            <a className="verweis" href="https://github.com/Mentox07/xera-ai" target="_blank" rel="noopener noreferrer">
              GitHub
            </a>
            . Wer nachsehen will, was mit seinen Eingaben geschieht, kann es
            nachlesen statt es zu glauben.
          </p>
        </div>
      </section>

      <section className="abschnitt">
        <h2>Was es nicht kann</h2>
        <div className="liste">
          {GRENZEN.map(([was, warum]) => (
            <div key={was}>
              <strong>{was}</strong>
              <p>{warum}</p>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
