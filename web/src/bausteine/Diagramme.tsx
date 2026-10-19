/** Die Erklärgrafiken.
 *
 * Von Hand gezeichnet, kein Bild und keine Bibliothek. Drei Gründe: Sie
 * folgen dem Aussehen mit (hell wie dunkel), sie bleiben bei jeder Größe
 * scharf, und sie wiegen zusammen weniger als ein einziges Bildschirmfoto.
 *
 * Jede zeigt einen **Vorgang**, keine Aufzählung. Ein Kasten mit „Modell"
 * darin sagt weniger als der Satz daneben; was zählt, ist der Weg, den etwas
 * nimmt, und was sich dabei ändert. Deshalb trägt jeder Pfeil eine
 * Beschriftung.
 */

import { SYSTEM, zahl } from "../daten/system";
import "./Diagramme.css";

const strich = "currentColor";

/** Gemeinsame Hülle: Pfeilspitze, Grundfarben, Zugänglichkeit. */
function Bild({
  breite,
  hoehe,
  titel,
  kennung,
  children,
}: {
  breite: number;
  hoehe: number;
  titel: string;
  kennung: string;
  children: React.ReactNode;
}) {
  return (
    <svg
      viewBox={`0 0 ${breite} ${hoehe}`}
      className="diagramm"
      /* Ohne dies fuellt sich jeder Pfad mit mehr als zwei Punkten schwarz —
         ein Linienzug wird dann zu einem Dreieck. Elemente mit eigenem fill
         oder einer CSS-Klasse sind davon nicht betroffen. */
      fill="none"
      role="img"
      aria-label={titel}
      preserveAspectRatio="xMidYMid meet"
    >
      <defs>
        <marker
          id={`spitze-${kennung}`}
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="5"
          markerHeight="5"
          orient="auto-start-reverse"
        >
          <path d="M0 0 L10 5 L0 10 z" fill={strich} />
        </marker>
      </defs>
      {children}
    </svg>
  );
}

/* ------------------------------------------------------------------------ */

/** 1. Aus Text werden Zahlen. */
export function DiagrammToken() {
  const stuecke = ["Wie", " voll", " ist", " die", " Platte", "?"];
  const zahlen = [7431, 3902, 651, 279, 18446, 30];
  return (
    <Bild breite={620} hoehe={190} kennung="tok" titel="Text wird in Stücke zerlegt und jedes Stück bekommt eine Zahl">
      <text x="0" y="14" className="d-marke">TEXT</text>
      <text x="0" y="44" className="d-mono d-hell">„Wie voll ist die Platte?"</text>

      <path d="M14 58 L14 78" stroke={strich} strokeWidth="1.2" markerEnd="url(#spitze-tok)" className="d-linie" />
      <text x="26" y="74" className="d-klein">zerlegen</text>

      <text x="0" y="102" className="d-marke">STÜCKE</text>
      {stuecke.map((s, i) => (
        <g key={s} transform={`translate(${i * 100}, 110)`}>
          <rect width="88" height="26" rx="4" className="d-kasten" />
          <text x="44" y="17" textAnchor="middle" className="d-mono">{s.trim()}</text>
        </g>
      ))}

      {stuecke.map((_, i) => (
        <path
          key={i}
          d={`M${i * 100 + 44} 140 L${i * 100 + 44} 158`}
          stroke={strich}
          strokeWidth="1.2"
          markerEnd="url(#spitze-tok)"
          className="d-linie"
        />
      ))}

      {zahlen.map((z, i) => (
        <text key={z} x={i * 100 + 44} y="180" textAnchor="middle" className="d-mono d-akzent">
          {z}
        </text>
      ))}
    </Bild>
  );
}

/** 2. Das Modell schätzt, was als Nächstes kommt. */
export function DiagrammVorhersage() {
  const kandidaten = [
    { wort: "voll", wert: 0.62 },
    { wort: "gross", wert: 0.14 },
    { wort: "leer", wert: 0.09 },
    { wort: "schnell", wert: 0.05 },
    { wort: "…", wert: 0.1 },
  ];
  return (
    <Bild breite={620} hoehe={230} kennung="vor" titel="Das Modell schätzt für jedes mögliche nächste Stück eine Wahrscheinlichkeit">
      <text x="0" y="14" className="d-marke">BISHER</text>
      <rect x="0" y="24" width="250" height="30" rx="5" className="d-kasten" />
      <text x="12" y="44" className="d-mono">Wie __</text>

      <path d="M256 39 L306 39" stroke={strich} strokeWidth="1.2" markerEnd="url(#spitze-vor)" className="d-linie" />
      <text x="264" y="30" className="d-klein">Modell</text>

      <text x="320" y="14" className="d-marke">WAS KÖNNTE FOLGEN</text>
      {kandidaten.map((k, i) => (
        <g key={k.wort} transform={`translate(320, ${24 + i * 34})`}>
          <text x="0" y="14" className="d-mono">{k.wort}</text>
          <rect x="72" y="4" width="160" height="12" rx="3" className="d-balken-grund" />
          <rect
            x="72"
            y="4"
            width={160 * k.wert}
            height="12"
            rx="3"
            className={i === 0 ? "d-balken-voll" : "d-balken"}
          />
          <text x="242" y="14" className="d-mono d-klein d-still">
            {Math.round(k.wert * 100)} %
          </text>
        </g>
      ))}

      <path d="M12 62 L12 196 L306 196" stroke={strich} strokeWidth="1.2" strokeDasharray="3 3" className="d-linie-schwach" />
      <path d="M306 196 L306 66" stroke={strich} strokeWidth="1.2" markerEnd="url(#spitze-vor)" className="d-linie-schwach" />
      <text x="24" y="212" className="d-klein d-still">
        das gewählte Stück hängt vorne wieder an — und alles beginnt von vorn
      </text>
    </Bild>
  );
}

/** 3. Der Kontext ist ein Fenster, das mitwandert. */
export function DiagrammKontext() {
  return (
    <Bild breite={620} hoehe={215} kennung="ktx" titel="Das Kontextfenster fasst eine feste Zahl an Stücken; Älteres fällt hinten heraus">
      <text x="0" y="12" className="d-marke">GESPRÄCH, VON LINKS NACH RECHTS</text>

      <rect x="0" y="46" width="120" height="54" rx="5" className="d-kasten-aus" />
      <text x="60" y="68" textAnchor="middle" className="d-klein d-still">ältere</text>
      <text x="60" y="84" textAnchor="middle" className="d-klein d-still">Nachrichten</text>

      <path d="M150 73 L128 73" stroke={strich} strokeWidth="1.4" markerEnd="url(#spitze-ktx)" className="d-linie-warn" />

      <rect x="158" y="40" width="364" height="66" rx="6" className="d-fenster" />
      <text x="340" y="60" textAnchor="middle" className="d-marke d-akzent">{zahl(SYSTEM.kontext)} STÜCKE PASSEN HINEIN</text>
      <text x="340" y="80" textAnchor="middle" className="d-mono">was das Modell sieht</text>
      <text x="340" y="97" textAnchor="middle" className="d-klein d-still">Systemprompt · Verlauf · deine Frage</text>

      <path d="M552 73 L530 73" stroke={strich} strokeWidth="1.4" markerEnd="url(#spitze-ktx)" className="d-linie" />

      <rect x="560" y="46" width="60" height="54" rx="5" className="d-kasten" />
      <text x="590" y="77" textAnchor="middle" className="d-klein">neu</text>

      <text x="0" y="130" className="d-klein d-warn">
        fällt heraus, sobald vorne etwas dazukommt
      </text>

      <line x1="0" y1="150" x2="620" y2="150" className="d-trenner" />

      <text x="0" y="176" className="d-klein d-still">
        Deshalb „vergisst" ein Modell den Anfang eines langen Gesprächs: Es steht
      </text>
      <text x="0" y="196" className="d-klein d-still">
        nicht mehr im Fenster. Nichts wird gelöscht — es wird nur nicht mehr gezeigt.
      </text>
    </Bild>
  );
}

/** 4. Quantisierung: warum das Modell in den Speicher passt. */
export function DiagrammQuantisierung() {
  return (
    <Bild breite={620} hoehe={210} kennung="qua" titel="Quantisierung verkleinert jede Zahl im Modell, wodurch das Ganze in weniger Speicher passt">
      <text x="0" y="14" className="d-marke">EINE ZAHL IM MODELL</text>

      <rect x="0" y="26" width="270" height="60" rx="6" className="d-kasten" />
      <text x="14" y="48" className="d-mono d-hell">0,3184627</text>
      <text x="14" y="68" className="d-klein d-still">16 Bit — wie trainiert</text>

      <path d="M282 56 L336 56" stroke={strich} strokeWidth="1.4" markerEnd="url(#spitze-qua)" className="d-linie" />
      <text x="286" y="46" className="d-klein d-akzent">gerundet</text>

      <rect x="350" y="26" width="270" height="60" rx="6" className="d-kasten-akzent" />
      <text x="364" y="48" className="d-mono d-hell">0,32</text>
      <text x="364" y="68" className="d-klein d-still">im Schnitt {SYSTEM.bitsImSchnitt} Bit — wie bei uns</text>

      <text x="0" y="118" className="d-marke">WAS DAS AUSMACHT</text>
      <g transform="translate(0,128)">
        <rect width="600" height="18" rx="4" className="d-balken-grund" />
        <rect width="600" height="18" rx="4" className="d-balken-blass" />
        <text x="606" y="13" textAnchor="end" className="d-mono d-klein">{SYSTEM.groesseRohGb} GB unverändert</text>
      </g>
      <g transform="translate(0,154)">
        <rect width="600" height="18" rx="4" className="d-balken-grund" />
        <rect width={Math.round((600 * SYSTEM.aufKartenGb) / SYSTEM.groesseRohGb)} height="18" rx="4" className="d-balken-voll" />
        <rect x={Math.round((600 * SYSTEM.aufKartenGb) / SYSTEM.groesseRohGb)} width={Math.round((600 * SYSTEM.imRamGb) / SYSTEM.groesseRohGb)} height="18" rx="4" className="d-balken-halb" />
        <text x={Math.round((600 * SYSTEM.groesseGb) / SYSTEM.groesseRohGb) + 10} y="13" className="d-mono d-klein d-akzent">{SYSTEM.groesseGb} GB — {SYSTEM.aufKartenGb} auf den Karten, {SYSTEM.imRamGb} im RAM</text>
      </g>
      <text x="0" y="196" className="d-klein d-still">
        Der Preis: Das Modell wird etwas ungenauer. Es antwortet weiter, aber schlechter.
      </text>
    </Bild>
  );
}

/** 5. Lesen ist schnell, Schreiben ist langsam. */
export function DiagrammTempo() {
  return (
    <Bild breite={620} hoehe={200} kennung="tmp" titel="Die Frage wird auf einen Schlag gelesen, die Antwort Stück für Stück geschrieben">
      <text x="0" y="14" className="d-marke">DEINE FRAGE — ALLE STÜCKE AUF EINMAL</text>
      <g transform="translate(0,24)">
        {Array.from({ length: 22 }, (_, i) => (
          <rect key={i} x={i * 27} width="22" height="24" rx="3" className="d-kasten-akzent" />
        ))}
      </g>
      <text x="0" y="70" className="d-mono d-klein d-akzent">{SYSTEM.lesenTs} Stück je Sekunde</text>
      <text x="150" y="70" className="d-klein d-still">
        alle Karten rechnen gleichzeitig daran
      </text>

      <line x1="0" y1="92" x2="620" y2="92" className="d-trenner" />

      <text x="0" y="118" className="d-marke">DIE ANTWORT — EIN STÜCK NACH DEM ANDEREN</text>
      <g transform="translate(0,128)">
        {Array.from({ length: 8 }, (_, i) => (
          <g key={i}>
            <rect x={i * 74} width="52" height="24" rx="3" className="d-kasten" />
            {i < 7 && (
              <path
                d={`M${i * 74 + 56} 12 L${i * 74 + 70} 12`}
                stroke={strich}
                strokeWidth="1.2"
                markerEnd="url(#spitze-tmp)"
                className="d-linie"
              />
            )}
          </g>
        ))}
      </g>
      <text x="0" y="174" className="d-mono d-klein">{SYSTEM.schreibenTs} Stück je Sekunde</text>
      <text x="150" y="174" className="d-klein d-still">
        jedes braucht das vorige — nichts geht gleichzeitig
      </text>
    </Bild>
  );
}

/** 6. Wie Xera aufgebaut ist. */
export function DiagrammAufbau() {
  const kaesten = [
    { x: 0, name: "Browser", unten: "bei dir", ton: "d-kasten" },
    { x: 165, name: "Xera", unten: "CT 203 · VLAN 70", ton: "d-kasten-akzent" },
    { x: 330, name: "llama.cpp", unten: "Port 8080", ton: "d-kasten-akzent" },
    { x: 495, name: `${SYSTEM.karten} GPU`, unten: `${SYSTEM.vramGb} GB VRAM`, ton: "d-kasten-ton" },
  ];
  return (
    <Bild breite={620} hoehe={230} kennung="auf" titel="Der Weg einer Frage vom Browser über den Anwendungsserver zum Modell auf den Grafikkarten">
      {kaesten.map((k, i) => (
        <g key={k.name}>
          <rect x={k.x} y="40" width="125" height="58" rx="6" className={k.ton} />
          <text x={k.x + 62} y="66" textAnchor="middle" className="d-mono d-hell">{k.name}</text>
          <text x={k.x + 62} y="84" textAnchor="middle" className="d-klein d-still">{k.unten}</text>
          {i < kaesten.length - 1 && (
            <path
              d={`M${k.x + 129} 69 L${k.x + 159} 69`}
              stroke={strich}
              strokeWidth="1.4"
              markerEnd="url(#spitze-auf)"
              className="d-linie"
            />
          )}
        </g>
      ))}

      <text x="127" y="34" className="d-klein d-still">Frage</text>
      <text x="292" y="34" className="d-klein d-still">baut zusammen</text>
      <text x="457" y="34" className="d-klein d-still">rechnet</text>

      {/* Rückweg */}
      <path d="M557 104 L557 130 L62 130 L62 106" stroke={strich} strokeWidth="1.4" markerEnd="url(#spitze-auf)" className="d-linie-akzent" />
      <text x="250" y="146" className="d-klein d-akzent">Antwort, Stück für Stück zurück</text>

      <line x1="0" y1="168" x2="620" y2="168" className="d-trenner" />
      <text x="0" y="192" className="d-klein d-still">
        Keine Linie führt aus diesem Bild heraus. Es gibt keinen fremden Anbieter,
      </text>
      <text x="0" y="210" className="d-klein d-still">
        weil es keine Stelle gibt, an der einer angeschlossen wäre.
      </text>
    </Bild>
  );
}

/** 7. Was ein Agent tut. */
export function DiagrammAgent() {
  return (
    <Bild breite={620} hoehe={250} kennung="agt" titel="Ein Agent kann Werkzeuge aufrufen; eingreifende Werkzeuge fragen vorher nach">
      <rect x="0" y="30" width="150" height="44" rx="6" className="d-kasten" />
      <text x="75" y="57" textAnchor="middle" className="d-mono">deine Frage</text>

      <path d="M154 52 L194 52" stroke={strich} strokeWidth="1.4" markerEnd="url(#spitze-agt)" className="d-linie" />

      <rect x="200" y="20" width="160" height="64" rx="6" className="d-kasten-akzent" />
      <text x="280" y="44" textAnchor="middle" className="d-mono d-hell">Modell</text>
      <text x="280" y="62" textAnchor="middle" className="d-klein d-still">was brauche ich?</text>

      <path d="M364 52 L404 52" stroke={strich} strokeWidth="1.4" markerEnd="url(#spitze-agt)" className="d-linie" />
      {/* über dem Pfeil: daneben ist kein Platz, das Wort lief ins Werkzeug-Kästchen */}
      <text x="384" y="13" textAnchor="middle" className="d-klein d-still">Werkzeug</text>

      <rect x="410" y="20" width="210" height="64" rx="6" className="d-kasten-ton" />
      <text x="515" y="44" textAnchor="middle" className="d-mono d-hell">df -h auf dem GPU-Server</text>
      <text x="515" y="62" textAnchor="middle" className="d-klein d-still">liest nur — läuft sofort</text>

      {/* Rueckweg mit Ergebnis */}
      <path d="M515 88 L515 108 L280 108 L280 90" stroke={strich} strokeWidth="1.4" markerEnd="url(#spitze-agt)" className="d-linie-akzent" />
      <text x="330" y="124" className="d-klein d-akzent">Ergebnis geht ans Modell zurück</text>

      <line x1="0" y1="146" x2="620" y2="146" className="d-trenner" />

      <text x="0" y="172" className="d-marke d-warn">WENN DAS WERKZEUG ETWAS VERÄNDERT</text>
      <rect x="0" y="182" width="620" height="52" rx="6" className="d-kasten-warn" />
      <text x="16" y="204" className="d-mono">systemctl restart docker</text>
      <text x="16" y="222" className="d-klein d-still">
        hält an und fragt dich — alle Angaben offen sichtbar, bevor etwas passiert
      </text>
    </Bild>
  );
}
