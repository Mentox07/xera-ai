/** Die Seite „CLI“: Xera im Terminal (seit 2026-10-19).
 *
 * Für Leute, die ein Terminal kennen, aber nicht wissen, wie Xera dort
 * hinkommt. Drei Fragen in dieser Reihenfolge: Was ist es, wohin geht was,
 * wie richte ich es ein. Danach die Grenzen — und wem das Werkzeug gehört:
 * OpenCode ist nicht von uns, das soll man hier lesen statt es zu raten.
 *
 * Die Befehle kommen aus daten/cli.ts, dieselben wie in den Einstellungen.
 */

import { Kopieren } from "../bausteine/Kopieren";
import { Marke } from "../bausteine/Marke";
import { Terminal } from "../bausteine/Terminal";
import { Zeichen } from "../bausteine/Zeichen";
import { CLI_GRENZEN, CLI_GRUNDLAST_TOKEN, CLI_SCHRITTE, CLI_VARIANTEN, OPENCODE } from "../daten/cli";
import { SYSTEM, zahl } from "../daten/system";
import { bewegungAus, useEinblenden } from "../stil/bewegung";
import "./Start.css";
import "./Cli.css";

const TITEL = "Xera im Terminal";
const BEISPIEL = 'opencode run -m xera/xera#hoch "Finde heraus, warum test_login.py fehlschlägt"';

const STATIONEN = [
  {
    zeichen: <Zeichen name="code" groesse={20} />,
    titel: "Dein Rechner",
    ort: "OpenCode",
    text: "Liest und schreibt deine Dateien und führt Befehle aus — in deinem Ordner, mit deinen Rechten. Die Gespräche speichert OpenCode bei dir.",
  },
  {
    zeichen: <Zeichen name="web" groesse={20} />,
    titel: "xera-app.com/v1",
    ort: "dein Schlüssel",
    text: "Der Schlüssel öffnet die Tür. Xera zählt Tokens und Zeit, die Inhalte speichern wir nicht.",
  },
  {
    zeichen: <Marke groesse={22} />,
    titel: "Xera",
    ort: SYSTEM.modell,
    text: "Rechnet auf eigener Hardware in der Schweiz. Im Code-Bereich im Web arbeitet dasselbe Gespann: OpenCode, nur auf unserem Server.",
  },
];

const GRENZEN: [string, string][] = [
  [
    "Die erste Nachricht braucht Anlauf",
    `OpenCode schickt mit jeder Nachricht rund ${zahl(CLI_GRUNDLAST_TOKEN)} Token Anleitung und Werkzeugbeschreibungen mit. Beim ersten Mal liest Xera alles — bei rund ${SYSTEM.lesenTs} Token je Sekunde knapp eine Minute. Danach liegt es im Zwischenspeicher, Folgefragen kommen in Sekunden. Die tok/s-Anzeige von OpenCode zählt das Einlesen mit und wirkt darum bei kurzen Antworten winzig.`,
  ],
  [
    "Ein Platz für alle",
    "Alle CLI-Nutzer teilen sich einen Rechenplatz. Fragen zwei gleichzeitig, wartet der zweite, bis der erste fertig ist.",
  ],
  [
    "Grenzen je Nutzer",
    `${CLI_GRENZEN.proMinute} Anfragen pro Minute, ${zahl(CLI_GRENZEN.proTag)} am Tag und ${zahl(CLI_GRENZEN.tokensProTag)} neu gelesene oder geschriebene Token am Tag. Was im Zwischenspeicher liegt, zählt nicht.`,
  ],
  [
    "Andere Modelle",
    "OpenCode bietet auch Modelle anderer Anbieter an, manche gratis. Wer eines davon wählt, schickt seinen Code dorthin. Xera heisst in OpenCode xera/xera.",
  ],
  [
    "Dein Schlüssel",
    "Nur für Pro-Nutzer. Xera zeigt ihn genau einmal und speichert nur einen Prüfwert. Widerrufen geht jederzeit in den Einstellungen.",
  ],
];

/** Ein Abschnitt, der beim Hineinscrollen einblendet (wie auf der Startseite). */
function Abschnitt({ className = "abschnitt", id, children }: { className?: string; id?: string; children: React.ReactNode }) {
  const { ref, sichtbar } = useEinblenden<HTMLElement>();
  return (
    <section ref={ref} id={id} className={`${className} einblenden${sichtbar ? " sichtbar" : ""}`}>
      {children}
    </section>
  );
}

function Befehl({ text }: { text: string }) {
  return (
    <div className="cli-befehl">
      <code>{text}</code>
      <Kopieren text={text} />
    </div>
  );
}

export function Cli({
  aufSchluessel,
  knopf,
  angemeldet,
}: {
  /** Gast: anmelden. Angemeldet: die App mit den Einstellungen öffnen. */
  aufSchluessel: () => void;
  knopf: string;
  angemeldet: boolean;
}) {
  const zumEinrichten = () =>
    document.getElementById("einrichten")?.scrollIntoView({ behavior: bewegungAus() ? "auto" : "smooth" });

  // Zwischen „Xera eintragen“ und „Schlüssel hinterlegen“ kommt der Schlüssel selbst —
  // in den Einstellungen gibt es dafür einen eigenen Knopf, hier einen Schritt.
  const [installieren, eintragen, hinterlegen, starten] = CLI_SCHRITTE;
  const schritte = [installieren!, eintragen!, null, hinterlegen!, starten!];

  return (
    <main className="seite cli-seite">
      <section className="aufschlag">
        <h1 aria-label={TITEL}>
          {TITEL.split("").map((b, i) => (
            <span key={i} className="buchstabe" style={{ "--i": i } as React.CSSProperties} aria-hidden="true">
              {b === " " ? " " : b}
            </span>
          ))}
        </h1>
        <p className="aufschlag-satz">
          OpenCode mit Xera als Modell. Xera liest deinen Code, schreibt Dateien und führt Befehle aus — auf deinem
          Rechner. Gerechnet wird bei uns.
        </p>
        <div className="aufschlag-knoepfe">
          <button type="button" className="knopf-voll" onClick={aufSchluessel}>
            {knopf}
          </button>
          <button type="button" className="knopf-text" onClick={zumEinrichten}>
            So richtest du es ein
            <Zeichen name="pfeil-rechts" groesse={14} />
          </button>
        </div>
      </section>

      <figure
        className="bild cli-bild"
        aria-label="Vorführung: Im Terminal wird opencode gestartet und eine Frage gestellt. Xera schreibt ein Skript, probiert es auf dem Rechner aus und antwortet."
      >
        <Terminal />
      </figure>

      <Abschnitt>
        <h2>So funktioniert’s</h2>
        <div className="weg">
          <span className="weg-paket" aria-hidden="true" />
          {STATIONEN.map((s, i) => (
            <article key={s.titel} className="weg-station" style={{ "--i": i } as React.CSSProperties}>
              <span className="weg-zeichen">{s.zeichen}</span>
              <h3>{s.titel}</h3>
              <p className="weg-ort">{s.ort}</p>
              <p>{s.text}</p>
            </article>
          ))}
        </div>
        <p className="notiz">
          Was OpenCode für eine Antwort braucht — deine Frage, Ausschnitte aus Dateien, Ausgaben von Befehlen —, geht
          an das Modell. Gespeichert wird davon nichts, nur je Anfrage Zeitpunkt, Anzahl Tokens und Dauer. Mehr in
          der{" "}
          <a className="verweis" href="/datenschutz">
            Datenschutzerklärung
          </a>
          .
        </p>
      </Abschnitt>

      <Abschnitt id="einrichten">
        <h2>Einrichten</h2>
        <p className="cli-vorab">Für Linux, macOS und Windows mit WSL. Fünf Schritte, einmal.</p>
        <ol className="cli-schritte">
          {schritte.map((s, i) => (
            <li key={s ? s.titel : "schluessel"} style={{ "--i": i } as React.CSSProperties}>
              <span className="cli-nr">{String(i + 1).padStart(2, "0")}</span>
              <div>
                {s ? (
                  <>
                    <h3>{s.titel}</h3>
                    <Befehl text={s.befehl} />
                  </>
                ) : (
                  <>
                    <h3>Schlüssel holen</h3>
                    <p>
                      In der App unter Einstellungen → CLI, für Pro-Nutzer. Er steht nur einmal da, also gleich
                      kopieren.{" "}
                      <button type="button" className="verweis" onClick={aufSchluessel}>
                        {angemeldet ? "Einstellungen öffnen" : "Anmelden"}
                      </button>
                    </p>
                  </>
                )}
              </div>
            </li>
          ))}
        </ol>
      </Abschnitt>

      <Abschnitt>
        <h2>Denkaufwand</h2>
        <p className="cli-vorab">
          Vier Stufen wie <code>/effort</code> im Web. Je höher, desto länger denkt Xera nach, bevor es loslegt —
          lohnt sich bei kniffligen Fehlern, nicht bei einer kurzen Frage. Ohne Stufe denkt Xera nicht eigens nach.
        </p>
        <div className="cli-stufen">
          {CLI_VARIANTEN.map((v, i) => (
            <code key={v} style={{ "--i": i } as React.CSSProperties}>
              xera/xera#{v}
            </code>
          ))}
        </div>
        <Befehl text={BEISPIEL} />
        <p className="notiz">Im laufenden OpenCode wechselst du die Stufe über den Varianten-Wechsel.</p>
      </Abschnitt>

      <Abschnitt>
        <h2>Gut zu wissen</h2>
        <div className="liste">
          {GRENZEN.map(([titel, text]) => (
            <div key={titel}>
              <strong>{titel}</strong>
              <p>{text}</p>
            </div>
          ))}
        </div>
      </Abschnitt>

      <Abschnitt>
        <h2>Gebaut auf OpenCode</h2>
        <div className="text fliesstext">
          <p>
            Das Programm im Terminal ist <em>OpenCode</em>, ein quelloffener Coding-Agent unter {OPENCODE.lizenz}
            -Lizenz — nicht von uns. Xera ist darin ein Anbieter wie andere auch, OpenCode selbst ist unverändert. Wer
            wissen will, was auf dem eigenen Rechner läuft, kann es dort nachlesen.
          </p>
        </div>
        <div className="cli-links">
          <a className="cli-link" href={OPENCODE.repo} target="_blank" rel="noopener noreferrer">
            <span className="cli-link-art">Quelltext auf GitHub</span>
            <span className="cli-link-name">{OPENCODE.repoName}</span>
            <Zeichen name="pfeil-rechts" groesse={14} />
          </a>
          <a className="cli-link" href={OPENCODE.doku} target="_blank" rel="noopener noreferrer">
            <span className="cli-link-art">Dokumentation</span>
            <span className="cli-link-name">opencode.ai/docs</span>
            <Zeichen name="pfeil-rechts" groesse={14} />
          </a>
        </div>
      </Abschnitt>

      <Abschnitt className="schluss">
        <p>{angemeldet ? "Den Schlüssel holst du in den Einstellungen." : "Anmeldung über Discord, Schlüssel für Pro-Nutzer."}</p>
        <button type="button" className="knopf-voll" onClick={aufSchluessel}>
          {knopf}
        </button>
      </Abschnitt>
    </main>
  );
}
