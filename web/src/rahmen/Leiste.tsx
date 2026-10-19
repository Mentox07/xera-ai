/** Die Leiste links: Bereichswechsel, Befehle, Modellstatus, Nutzer.
 *
 * Zwei Breiten. Schmal (Standard) nur mit Zeichen — wer das Werkzeug täglich
 * benutzt, kennt die vier Plätze nach einem Tag; die Bedeutung steht dann in
 * der Fahne beim Überfahren. Breit mit Beschriftung, für die ersten Tage und
 * für alle, die lieber lesen als sich merken. Die Wahl bleibt gespeichert.
 *
 * Auf dem Handy wird die Leiste zur Leiste unten (Leiste.css).
 */

import type { Bereich } from "./bereiche";
import type { BereichsId, Nutzer } from "../daten/typen";
import { Marke } from "../bausteine/Marke";
import { Zeichen } from "../bausteine/Zeichen";
import { Modellstatus } from "./Modellstatus";
import "./Leiste.css";

interface Eigenschaften {
  bereiche: Bereich[];
  aktiv: BereichsId;
  aufWechsel: (id: BereichsId) => void;
  nutzer: Nutzer | null;
  aufPalette: () => void;
  breit: boolean;
  aufBreite: () => void;
  aufEinstellungen: () => void;
  aufStartseite: () => void;
}

export function Leiste({
  bereiche,
  aktiv,
  aufWechsel,
  nutzer,
  aufPalette,
  breit,
  aufBreite,
  aufEinstellungen,
  aufStartseite,
}: Eigenschaften) {
  const index = Math.max(0, bereiche.findIndex((b) => b.id === aktiv));

  return (
    <nav className={"leiste" + (breit ? " breit" : "")} aria-label="Bereiche">
      <a
        className="leiste-marke"
        href="/app/start"
        title="Startseite, How Xera works, Über uns"
        onClick={(e) => {
          e.preventDefault();
          aufStartseite();
        }}
      >
        <Marke groesse={28} />
        {breit && <span className="leiste-marke-name">Xera</span>}
      </a>

      <ul className="leiste-liste" style={{ "--index": index } as React.CSSProperties}>
        {/* Die Markierung ist ein eigenes Element und wandert zum aktiven
            Platz, statt an einem Knopf zu verschwinden und am anderen
            aufzutauchen. So sieht man, wohin man gewechselt ist. */}
        <span className="leiste-zeiger" aria-hidden="true" />
        {bereiche.map((b) => (
          <li key={b.id}>
            <button
              type="button"
              className={"leiste-knopf" + (aktiv === b.id ? " ist-aktiv" : "")}
              onClick={() => aufWechsel(b.id)}
              title={breit ? `${b.kurz}  (Strg ${b.taste})` : undefined}
              aria-current={aktiv === b.id ? "page" : undefined}
            >
              <Zeichen name={b.id} />
              <span className="leiste-name">
                {b.name}
                {!breit && <kbd>Strg {b.taste}</kbd>}
              </span>
              {breit && <kbd className="leiste-taste">{b.taste}</kbd>}
            </button>
          </li>
        ))}
      </ul>

      <div className="leiste-fuss">
        <Modellstatus breit={breit} />

        <button type="button" className="leiste-knopf" onClick={aufPalette}>
          <Zeichen name="befehl" />
          <span className="leiste-name">
            Befehle
            {!breit && <kbd>Strg K</kbd>}
          </span>
          {breit && <kbd className="leiste-taste">K</kbd>}
        </button>

        <button type="button" className="leiste-knopf leiste-nur-gross" onClick={aufBreite}>
          <Zeichen name="leiste" />
          <span className="leiste-name">{breit ? "Leiste schmal" : "Leiste breit"}</span>
        </button>

        {nutzer && (
          <button type="button" className="leiste-nutzer-knopf" onClick={aufEinstellungen} title="Konto und Einstellungen">
            <span className="leiste-nutzer">
              {nutzer.avatar ? (
                <img
                  src={`https://cdn.discordapp.com/avatars/${nutzer.id}/${nutzer.avatar}.png?size=64`}
                  alt=""
                  width={26}
                  height={26}
                />
              ) : (
                <span aria-hidden="true">{nutzer.username.slice(0, 2).toUpperCase()}</span>
              )}
            </span>
            {breit && (
              <span className="leiste-nutzer-text">
                <strong>{nutzer.username}</strong>
                <small>{nutzer.is_admin ? "Admin" : nutzer.is_pro ? "Pro" : "Gratis"}</small>
              </span>
            )}
            <span className="nur-vorlesen">Angemeldet als {nutzer.username}</span>
          </button>
        )}
      </div>
    </nav>
  );
}
