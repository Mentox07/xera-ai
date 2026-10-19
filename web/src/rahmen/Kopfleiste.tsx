/** Die Kopfleiste der öffentlichen Seiten.
 *
 * Vier Punkte, mehr nicht. Eine Navigation, die alles anbietet, hilft
 * niemandem — sie zwingt jeden dazu, erst zu lesen, was es überhaupt gibt.
 * „CLI“ kam am 2026-10-19 dazu: Xera im Terminal ist ein eigener Weg
 * hinein, kein Unterpunkt der App.
 */

import { Marke } from "../bausteine/Marke";
import "./Kopfleiste.css";

export type Seite = "start" | "wie" | "cli" | "ueber";

const PUNKTE: { id: Seite; name: string }[] = [
  { id: "start", name: "Xera" },
  { id: "wie", name: "How Xera works" },
  { id: "cli", name: "CLI" },
  { id: "ueber", name: "Über uns" },
];

interface Eigenschaften {
  aktiv: Seite;
  aufWechsel: (s: Seite) => void;
  aufAnmelden: () => void;
  /** Beschriftung des Knopfs rechts; angemeldet „Zur App →“. */
  knopf?: string;
}

export function Kopfleiste({ aktiv, aufWechsel, aufAnmelden, knopf = "Anmelden" }: Eigenschaften) {
  return (
    <header className="kopfleiste">
      <button
        type="button"
        className="kopf-marke"
        onClick={() => aufWechsel("start")}
        aria-label="Zur Startseite"
      >
        <Marke groesse={26} />
      </button>

      <nav aria-label="Seiten">
        {PUNKTE.map((p) => (
          <button
            key={p.id}
            type="button"
            className={aktiv === p.id ? "ist-aktiv" : ""}
            onClick={() => aufWechsel(p.id)}
            aria-current={aktiv === p.id ? "page" : undefined}
          >
            {p.name}
          </button>
        ))}
      </nav>

      <button type="button" className="kopf-anmelden" onClick={aufAnmelden}>
        {knopf}
      </button>
    </header>
  );
}
