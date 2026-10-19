/** „Wie das funktioniert“ — der Lernteil.
 *
 * Gedacht für jemanden, der noch nie mit einem Sprachmodell zu tun hatte und
 * wissen will, was da eigentlich passiert. Kein Fachtext: Jeder Abschnitt
 * beginnt mit dem Bild und erklärt es dann in Sätzen, die ohne Vorwissen
 * auskommen.
 *
 * Die Zahlen sind die unseres Servers (aus `daten/system.ts`). Das ist der Punkt: Wer „131 072 Stücke“
 * neben dem eigenen Chatfenster sieht, versteht die Grenze anders als bei
 * einer abstrakten Erklärung.
 */

import { SYSTEM, zahl } from "../daten/system";
import { useEinblenden } from "../stil/bewegung";
import {
  DiagrammAgent,
  DiagrammAufbau,
  DiagrammKontext,
  DiagrammQuantisierung,
  DiagrammTempo,
  DiagrammToken,
  DiagrammVorhersage,
} from "../bausteine/Diagramme";
import "./Lernen.css";

interface Kapitel {
  nr: string;
  titel: string;
  frage: string;
  bild: React.ReactNode;
  text: React.ReactNode;
  /** Etwas zum Selberprobieren. Nichts erklärt so gut wie eine Beobachtung. */
  probier?: string;
}

const KAPITEL: Kapitel[] = [
  {
    nr: "01",
    titel: "Ein Modell liest keine Wörter",
    frage: "Was passiert mit deinem Satz, bevor das Modell ihn sieht?",
    bild: <DiagrammToken />,
    text: (
      <>
        <p>
          Ein Sprachmodell rechnet. Rechnen kann man nur mit Zahlen, also wird
          dein Satz zuerst in Stücke zerlegt, und jedes Stück bekommt eine
          Nummer aus einem festen Verzeichnis.
        </p>
        <p>
          Die Stücke sind <strong>keine Wörter</strong>. Häufige Wörter sind
          oft ein Stück, seltene zerfallen in mehrere. „Platte“ ist eines,
          „Quantisierung“ sind vier. Deshalb kostet ein deutscher Text mehr
          Stücke als derselbe Text auf Englisch — das Verzeichnis wurde
          überwiegend an englischem Material gebaut.
        </p>
        <p>
          Wenn du irgendwo von <em>Token</em> liest: Das sind diese Stücke.
          Alles, was ein Modell kostet und begrenzt, wird darin gemessen.
        </p>
      </>
    ),
    probier: "Frag Xera: „Zerlege das Wort Donaudampfschifffahrt in Tokens.“ Dann dasselbe mit „cat“.",
  },
  {
    nr: "02",
    titel: "Es rät, was als Nächstes kommt",
    frage: "Woher weiss das Modell, was es antworten soll?",
    bild: <DiagrammVorhersage />,
    text: (
      <>
        <p>
          Es weiss es nicht. Es schätzt. Für jedes mögliche nächste Stück
          berechnet das Modell, wie gut es passt — und nimmt dann eines der
          wahrscheinlichen. Danach hängt es dieses Stück an den Text an und
          rechnet von vorne.
        </p>
        <p>
          Das ist der ganze Vorgang. Ein Satz mit vierzig Stücken entsteht in
          vierzig Durchläufen, und in jedem sieht das Modell alles, was bisher
          dasteht.
        </p>
        <p>
          Daraus folgt zweierlei. Erstens:{" "}
          <strong>Es gibt keinen Plan.</strong> Das Modell weiss am Anfang eines
          Satzes nicht, wie er endet. Zweitens: Es kann Unsinn erzeugen, der
          völlig sicher klingt — denn „passt gut“ heisst nicht „stimmt“.
        </p>
      </>
    ),
    probier: "Stell dieselbe Frage zweimal in zwei neuen Gesprächen. Die Antworten sind ähnlich, aber nicht gleich.",
  },
  {
    nr: "03",
    titel: "Das Gedächtnis ist ein Fenster",
    frage: "Warum vergisst es den Anfang langer Gespräche?",
    bild: <DiagrammKontext />,
    text: (
      <>
        <p>
          Das Modell hat kein Gedächtnis zwischen den Durchläufen. Was es
          „weiss“, steht in dem Text, den es gerade vorgelegt bekommt — und
          dieser Text hat eine feste Obergrenze. Bei uns sind es{" "}
          <strong>{zahl(SYSTEM.kontext)} Stücke</strong>.
        </p>
        <p>
          Da hinein muss alles: die Anweisung an das Modell, der bisherige
          Verlauf, deine neue Frage und der Platz für die Antwort. Wird es
          voll, fällt der Anfang heraus.
        </p>
        <p>
          Xera lässt es nicht so weit kommen: Ist das Fenster zu 85 Prozent
          gefüllt, fasst das Modell den älteren Teil des Gesprächs zusammen
          und behält nur die letzten Nachrichten wörtlich. Was in der
          Zusammenfassung fehlt, ist danach für das Modell weg.
        </p>
        <p>
          Deshalb ist ein neues Gespräch für eine neue Frage kein Umstand,
          sondern der richtige Griff: Alles, was noch im Fenster steht, kostet
          Platz und Zeit — auch das, was nicht mehr zur Sache gehört.
        </p>
      </>
    ),
    probier: "Führ ein sehr langes Gespräch und frag am Ende nach deiner ersten Nachricht.",
  },
  {
    nr: "04",
    titel: `${SYSTEM.parameterMrd} Milliarden in ${SYSTEM.groesseGb} Gigabyte`,
    frage: "Wie passt ein Modell dieser Grösse auf fünf gebrauchte Karten?",
    bild: <DiagrammQuantisierung />,
    text: (
      <>
        <p>
          Ein Modell besteht aus Zahlen — bei diesem sind es {SYSTEM.parameterMrd} Milliarden,
          dazu eine Nachschlagetabelle mit weiteren {SYSTEM.tabelleMrd} Milliarden. Beim
          Training ist jede davon 16 Bit gross. Das Ganze wöge damit rund{" "}
          {SYSTEM.groesseRohGb} Gigabyte und passte auf keine Karte, die wir haben.
        </p>
        <p>
          <strong>Quantisierung</strong> rundet diese Zahlen. Statt 0,3184627 wird 0,32
          gespeichert, im Schnitt mit {SYSTEM.bitsImSchnitt} Bit statt sechzehn. Das Modell
          schrumpft auf {SYSTEM.groesseGb} Gigabyte.
        </p>
        <p>
          Das sind immer noch mehr als die {SYSTEM.vramGb} Gigabyte der Karten. Deshalb liegt
          die Nachschlagetabelle — {SYSTEM.imRamGb} Gigabyte — im Arbeitsspeicher. Aus ihr
          wird je Stück nur eine Zeile gelesen, nicht gerechnet; das geht auch dort schnell.
          Auf den Karten bleiben {SYSTEM.aufKartenGb} Gigabyte, und die passen.
        </p>
        <p>
          Umsonst ist das nicht: Jede Rundung ist ein kleiner Fehler, und über so viele
          Zahlen summiert sich das. Das Modell antwortet weiter, aber etwas ungenauer als
          das Original. Das ist der Handel — und wer ihn kennt, wundert sich nicht über den
          gelegentlichen Fehlgriff.
        </p>
      </>
    ),
  },
  {
    nr: "05",
    titel: "Lesen ist schnell, Schreiben ist langsam",
    frage: "Warum dauert die Antwort, obwohl die Frage sofort verstanden war?",
    bild: <DiagrammTempo />,
    text: (
      <>
        <p>
          Deine Frage kann das Modell <strong>auf einen Schlag</strong> lesen.
          Alle Stücke sind schon da, also rechnen alle Karten gleichzeitig
          daran. Bei uns sind das rund {SYSTEM.lesenTs} Stücke je Sekunde.
        </p>
        <p>
          Beim Antworten geht das nicht. Jedes Stück braucht alle vorherigen —
          das zwanzigste Wort kann erst entstehen, wenn das neunzehnte
          feststeht. Nichts lässt sich vorziehen. Deshalb nur rund {SYSTEM.schreibenTs} Stücke
          je Sekunde, etwa {Math.round(SYSTEM.lesenTs / SYSTEM.schreibenTs)}-mal langsamer.
          Dass es überhaupt so schnell geht, liegt daran, dass das Modell je Stück nur{" "}
          {SYSTEM.aktivMrd} seiner {SYSTEM.parameterMrd} Milliarden Zahlen braucht — für
          jedes Stück wählt es die passenden „Experten“ aus.
        </p>
        <p>
          Genau darum siehst du die Antwort Wort für Wort erscheinen. Das ist
          keine Spielerei der Oberfläche, sondern der Vorgang selbst.
        </p>
      </>
    ),
    probier: "Stell eine Frage mit einer sehr langen Antwort und eine mit einer sehr kurzen. Die Wartezeit bis zum ersten Wort ist fast gleich.",
  },
  {
    nr: "06",
    titel: "Wie Xera aufgebaut ist",
    frage: "Was passiert zwischen deinem Browser und den Grafikkarten?",
    bild: <DiagrammAufbau />,
    text: (
      <>
        <p>
          Vier Stationen. Der Browser schickt deine Frage an den
          Anwendungsserver. Der baut die Anweisung zusammen — Verlauf,
          Werkzeuge, die Dateien des Gesprächs — und reicht alles an llama.cpp
          weiter, das Programm, das das Modell tatsächlich rechnet. Das
          verteilt die Arbeit auf {SYSTEM.kartenWort} Grafikkarten.
        </p>
        <p>
          llama.cpp hält sechs Plätze bereit: je einen für den Chat und für
          Code und Cowork, die übrigen für Agents, Homelab und Nebenaufgaben.
          Was ein Platz schon gelesen hat, bleibt dort liegen — deshalb kommt
          die Antwort auf eine Folgefrage schneller als auf die erste.
        </p>
        <p>
          Der Rückweg läuft Stück für Stück: Sobald ein Wort feststeht, geht es
          zurück bis in deinen Browser. Deshalb siehst du es sofort und nicht
          erst am Ende.
        </p>
        <p>
          <strong>Keine Linie führt aus diesem Bild heraus.</strong> Es gibt
          keinen fremden Anbieter, weil es keine Stelle gibt, an der einer
          angeschlossen wäre.
        </p>
      </>
    ),
  },
  {
    nr: "07",
    titel: "Wenn das Modell etwas tun soll",
    frage: "Wie kommt es an Daten, die es nicht wissen kann?",
    bild: <DiagrammAgent />,
    text: (
      <>
        <p>
          Wie voll die Platte auf einem Server ist, kann kein Modell wissen —
          das steht in keinem Trainingsmaterial. Also bekommt es{" "}
          <strong>Werkzeuge</strong>: kleine Befehle, die es aufrufen darf.
        </p>
        <p>
          Der Ablauf ist eine Schleife. Das Modell sagt, welches Werkzeug es
          mit welchen Angaben braucht. Der Server führt es aus und legt das
          Ergebnis in den Text zurück. Dann rechnet das Modell weiter — jetzt
          mit einer Tatsache statt einer Vermutung.
        </p>
        <p>
          Für grössere Aufgaben beauftragt das Modell <strong>Agents</strong> —
          bis zu vier arbeiten gleichzeitig, jeder mit eigenem Auftrag. Ihre
          Dateien liegen in einem Arbeitsordner, der zum Gespräch gehört. Dort
          schreiben, ändern und testen sie, ohne Netz und ohne Zugriff auf den
          Server. Eine Webseite oder ein Spiel öffnet Xera dort in einem echten
          Browser und meldet, ob Fehler auftreten.
        </p>
        <p>
          Nur im Homelab-Bereich greifen Werkzeuge auf echte Server zu. Was
          dort nur liest, läuft sofort. Was etwas verändert, hält an und fragt
          dich — mit allen Angaben offen sichtbar. Was auf einem echten Server
          passiert, soll niemand versehentlich auslösen.
        </p>
      </>
    ),
    probier: "Lade im Code-Bereich eine Excel-Datei hoch und bitte Xera, eine Spalte zu ergänzen. Sieh zu, welche Werkzeuge aufgerufen werden.",
  },
];

/** Ein Kapitel blendet ein, sobald es ins Bild kommt — und erst dann
 *  zeichnen sich die Linien seines Diagramms (bewegung.css). */
function Kapitel({ k }: { k: (typeof KAPITEL)[number] }) {
  const { ref, sichtbar } = useEinblenden<HTMLElement>(0.12);
  return (
    <article ref={ref} id={`k${k.nr}`} className={"kapitel einblenden" + (sichtbar ? " sichtbar" : "")}>
      <div className="kapitel-kopf">
        <span className="kapitel-nr zahlen">{k.nr}</span>
        <div>
          <h2>{k.titel}</h2>
          <p className="kapitel-frage">{k.frage}</p>
        </div>
      </div>

      <figure className="kapitel-bild">{k.bild}</figure>

      <div className="kapitel-text fliesstext">{k.text}</div>

      {k.probier && (
        <aside className="kapitel-probier">
          <span className="marke">Selbst ausprobieren</span>
          <p>{k.probier}</p>
        </aside>
      )}
    </article>
  );
}

export function Lernen({ aufZurueck }: { aufZurueck: () => void }) {
  return (
    <div className="lernen">
      <main>
        <section className="lernen-aufschlag">
          <span className="marke">Für alle, die es genauer wissen wollen</span>
          <h1>Wie ein Sprachmodell arbeitet</h1>
          <p className="lernen-lead">
            Sieben Kapitel, jedes mit einem Bild. Kein Vorwissen nötig. Die
            Zahlen stammen von dem Server, auf dem Xera läuft — du kannst also
            nebenher ausprobieren, was hier steht.
          </p>
          <nav className="lernen-inhalt" aria-label="Kapitel">
            {KAPITEL.map((k) => (
              <a key={k.nr} href={`#k${k.nr}`}>
                <span className="zahlen">{k.nr}</span>
                {k.titel}
              </a>
            ))}
          </nav>
        </section>

        {KAPITEL.map((k) => (
          <Kapitel key={k.nr} k={k} />
        ))}

        <section className="lernen-schluss">
          <h2>Und jetzt?</h2>
          <p>
            Das Beste an einem Modell im eigenen Haus ist, dass man daran
            herumprobieren kann, ohne dass es etwas kostet. Stell ihm eine
            Frage, bei der du die Antwort kennst — und schau, wo es danebenliegt.
            Das lernt man aus keinem Text.
          </p>
          <button type="button" className="knopf-voll" onClick={aufZurueck}>
            Zurück zur Startseite
          </button>
        </section>
      </main>
    </div>
  );
}
