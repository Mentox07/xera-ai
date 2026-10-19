/** Die Startseite.
 *
 * Dritter Anlauf. Der erste war ein Datenblatt, der zweite hatte zu viel
 * Werbung darin — „läuft im Nebenraum" stimmt für einen einzigen Menschen,
 * und wer die Seite von woanders aufruft, liest darüber hinweg oder ärgert
 * sich. Dasselbe gilt für die Beteuerungen, wie sicher alles sei: Wer das
 * dauernd sagt, klingt, als müsste er es sagen.
 *
 * Jetzt: was es ist, wie es aussieht, wie man hineinkommt. Der Rest steht auf
 * den beiden anderen Seiten, für die, die es wissen wollen.
 */

import { Zeichen } from "../bausteine/Zeichen";
import { SYSTEM, zahl } from "../daten/system";
import { Vorfuehrung } from "../bausteine/Vorfuehrung";
import { useEinblenden, useZaehler } from "../stil/bewegung";
import "./Start.css";

const BEREICHE = [
  { id: "chat" as const, name: "Chat", text: "Fragen, Recherche im Netz, Dokumente lesen. Auf Wunsch mit Denkmodus." },
  { id: "cowork" as const, name: "Cowork", text: "Ein Arbeitsbereich je Vorhaben, mit Dateien, Notizen und Agents, die mitarbeiten." },
  { id: "code" as const, name: "Code", text: "Programme schreiben, umbauen, Fehler suchen. Webseiten und Spiele testet Xera im Browser." },
  { id: "homelab" as const, name: "Homelab", text: "Server und Container verwalten. Braucht eine Rolle." },
];

/** Ein Abschnitt, der beim Hineinscrollen einblendet; seine Kinder laufen
 *  versetzt ein (bewegung in Start.css). */
function Abschnitt({ className, children }: { className: string; children: React.ReactNode }) {
  const { ref, sichtbar } = useEinblenden<HTMLElement>();
  return (
    <section ref={ref} className={`${className} einblenden${sichtbar ? " sichtbar" : ""}`}>
      {children}
    </section>
  );
}

/** Eine gemessene Zahl, die beim ersten Sichtbarwerden hochzählt. */
function Zahl({ wert, los }: { wert: number; los: boolean }) {
  const jetzt = useZaehler(wert, los);
  return <span className="zahl-zaehlt">{zahl(jetzt)}</span>;
}

function Modelldaten({ aufWie }: { aufWie: () => void }) {
  const { ref, sichtbar } = useEinblenden<HTMLElement>(0.3);
  return (
    <section ref={ref} className={`abschnitt einblenden${sichtbar ? " sichtbar" : ""}`}>
      <h2>Modell</h2>
      <div className="kacheln">
        <div className="kachel">
          <span className="kachel-wert"><Zahl wert={SYSTEM.kontext} los={sichtbar} /></span>
          <span className="kachel-name">Token Kontext je Gespräch</span>
        </div>
        <div className="kachel">
          <span className="kachel-wert">~<Zahl wert={SYSTEM.schreibenTs} los={sichtbar} /></span>
          <span className="kachel-name">Token/s beim Schreiben</span>
        </div>
        <div className="kachel">
          <span className="kachel-wert"><Zahl wert={SYSTEM.lesenTs} los={sichtbar} /></span>
          <span className="kachel-name">Token/s beim Lesen</span>
        </div>
        <div className="kachel">
          <span className="kachel-wert"><Zahl wert={SYSTEM.vramGb} los={sichtbar} /> GB</span>
          <span className="kachel-name">VRAM auf {SYSTEM.kartenWort} Karten</span>
        </div>
      </div>
      <dl className="daten">
        <div>
          <dt>Modell</dt>
          <dd>
            {SYSTEM.modell}, quantisiert auf {SYSTEM.quantisierung} — {SYSTEM.parameterMrd} Milliarden
            Parameter, davon {SYSTEM.aktivMrd} je Stück aktiv
          </dd>
        </div>
        <div>
          <dt>Hardware</dt>
          <dd>{SYSTEM.kartenText}</dd>
        </div>
      </dl>
      <p className="notiz">
        Gemessen am {SYSTEM.gemessenAm}. Was diese Zahlen bedeuten, steht unter{" "}
        <button type="button" className="verweis" onClick={aufWie}>
          How Xera works
        </button>
        .
      </p>
    </section>
  );
}

export function Start({
  aufAnmelden,
  aufWie,
  knopf = "Anmelden",
}: {
  aufAnmelden: () => void;
  aufWie: () => void;
  /** Angemeldet: „Zur App“. */
  knopf?: string;
}) {
  return (
    <main className="seite">
      <section className="aufschlag">
        <h1 aria-label="Xera AI">
          {"Xera AI".split("").map((b, i) => (
            <span key={i} className="buchstabe" style={{ "--i": i } as React.CSSProperties} aria-hidden="true">
              {b === " " ? "\u00a0" : b}
            </span>
          ))}
        </h1>
        <p className="aufschlag-satz">
          Ein Sprachmodell auf eigener Hardware, mit einer Oberfläche zum
          Arbeiten damit.
        </p>
        <div className="aufschlag-knoepfe">
          <button type="button" className="knopf-voll" onClick={aufAnmelden}>
            {knopf}
          </button>
          <button type="button" className="knopf-text" onClick={aufWie}>
            Wie es funktioniert
            <Zeichen name="pfeil-rechts" groesse={14} />
          </button>
        </div>
      </section>

      <figure className="bild" aria-label="Vorführung: eine Frage wird gestellt, die Antwort baut sich mit einer Tabelle auf.">
        <Vorfuehrung />
      </figure>

      <Abschnitt className="abschnitt">
        <h2>Bereiche</h2>
        <div className="raster">
          {BEREICHE.map((b, i) => (
            <article key={b.id} style={{ "--i": i } as React.CSSProperties}>
              <Zeichen name={b.id} groesse={18} />
              <h3>{b.name}</h3>
              <p>{b.text}</p>
            </article>
          ))}
        </div>
      </Abschnitt>

      <Modelldaten aufWie={aufWie} />

      <Abschnitt className="schluss">
        <p>{knopf === "Anmelden" ? "Anmeldung über Discord." : "Du bist angemeldet."}</p>
        <button type="button" className="knopf-voll" onClick={aufAnmelden}>
          {knopf}
        </button>
      </Abschnitt>
    </main>
  );
}
