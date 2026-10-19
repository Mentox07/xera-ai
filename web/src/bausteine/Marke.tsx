/** Das Zeichen von Xera.
 *
 * Das echte Bild aus `static/assets/xera-logo.png`, nicht nachgezeichnet.
 * Mein erster Versuch war ein SVG-Nachbau — er traf die Form nicht, weil das
 * Original aus zwei versetzten X besteht und aus einem Verlauf, den zwei
 * Pfade nicht hergeben.
 *
 * Zugeschnitten und verkleinert statt per CSS aus dem Original gerückt: Die
 * Datei ist 1254×1254 und 744 KB, für 26 Pixel in der Leiste ist das absurd.
 * Der Ausschnitt wiegt 20 KB, der Schriftzug 164 KB.
 *
 * Auf dunkler Kachel, weil das Bild einen schwarzen Grund hat — genau wie
 * `.x-mark` in der alten Oberfläche. Ohne Kachel steht im hellen Aussehen ein
 * schwarzer Klotz auf weißem Grund.
 */

import marke from "../mittel/marke.png";
import schriftzug from "../mittel/schriftzug.png";
import "./Marke.css";

interface Eigenschaften {
  groesse?: number;
  /** Mit „XERA AI" daneben. Für Anmeldung und Startseite. */
  mitSchrift?: boolean;
  className?: string;
}

export function Marke({ groesse = 28, mitSchrift = false, className }: Eigenschaften) {
  if (mitSchrift) {
    return (
      <span className={"marke-kachel ist-breit " + (className ?? "")}>
        <img src={schriftzug} alt="Xera AI" style={{ height: groesse }} />
      </span>
    );
  }

  return (
    <span
      className={"marke-kachel " + (className ?? "")}
      style={{ width: groesse, height: groesse }}
    >
      <img src={marke} alt="Xera" width={groesse} height={groesse} />
    </span>
  );
}
