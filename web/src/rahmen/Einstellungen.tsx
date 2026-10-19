/** Konto und Einstellungen — als Tafel, die von links hereingleitet.
 *
 * Wenig, aber vollständig: wer man ist und was man darf, wie es aussieht,
 * welche Tasten es gibt, und seit 2026-10-17 der Schlüssel für die CLI. Mehr
 * Einstellungen hat die Oberfläche nicht, und das ist Absicht.
 */

import { useEffect } from "react";
import type { Nutzer } from "../daten/typen";
import { QUELLTEXT, SYSTEM, zahl } from "../daten/system";
import { Zeichen } from "../bausteine/Zeichen";
import { CliZugang } from "./CliZugang";
import "./Einstellungen.css";

interface Eigenschaften {
  offen: boolean;
  aufSchliessen: () => void;
  nutzer: Nutzer;
  thema: string;
  aufThema: () => void;
  breit: boolean;
  aufBreite: () => void;
}

const TASTEN: [string, string][] = [
  ["Strg K", "Befehlspalette — auch Gespräche suchen"],
  ["Strg 1 … 4", "Bereich wechseln"],
  ["Strg Alt N", "Neues Gespräch"],
  ["Strg B", "Leiste breit / schmal"],
  ["Strg /", "Diese Übersicht"],
  ["Enter", "Senden"],
  ["Umschalt Enter", "Neue Zeile"],
  ["Strg V", "Bild aus der Zwischenablage anhängen"],
  ["Esc", "Antwort abbrechen, Fenster schliessen"],
];

export function Einstellungen({ offen, aufSchliessen, nutzer, thema, aufThema, breit, aufBreite }: Eigenschaften) {
  useEffect(() => {
    if (!offen) return;
    const taste = (e: KeyboardEvent) => e.key === "Escape" && aufSchliessen();
    window.addEventListener("keydown", taste);
    return () => window.removeEventListener("keydown", taste);
  }, [offen, aufSchliessen]);

  if (!offen) return null;

  const rolle = nutzer.is_admin ? "Admin" : nutzer.is_pro ? "Pro" : "Gratis";
  const unbegrenzt = nutzer.is_pro || nutzer.is_admin || nutzer.prompts_remaining < 0;

  return (
    <div className="einst-grund" onMouseDown={(e) => e.target === e.currentTarget && aufSchliessen()}>
      <aside className="einst" role="dialog" aria-modal="true" aria-label="Konto und Einstellungen">
        <header className="einst-kopf">
          <h2>Konto und Einstellungen</h2>
          <button type="button" onClick={aufSchliessen} aria-label="Schliessen">
            <Zeichen name="kreuz" groesse={14} />
          </button>
        </header>

        <section className="einst-teil" style={{ "--i": 0 } as React.CSSProperties}>
          <div className="einst-konto">
            <span className="einst-bild">
              {nutzer.avatar ? (
                <img src={`https://cdn.discordapp.com/avatars/${nutzer.id}/${nutzer.avatar}.png?size=96`} alt="" />
              ) : (
                nutzer.username.slice(0, 2).toUpperCase()
              )}
            </span>
            <div>
              <strong>{nutzer.username}</strong>
              <span className="einst-rolle">{rolle}</span>
              {nutzer.has_homelab && <span className="einst-rolle ist-homelab">Homelab</span>}
            </div>
          </div>
          <p className="einst-zeile">
            {unbegrenzt ? "Unbegrenzte Fragen." : `${nutzer.prompts_remaining} von ${nutzer.limit} Fragen heute übrig.`}
          </p>
        </section>

        <section className="einst-teil" style={{ "--i": 1 } as React.CSSProperties}>
          <h3>Ansicht</h3>
          <label className="einst-schalter">
            <span>Helles Aussehen</span>
            <input type="checkbox" checked={thema === "light"} onChange={aufThema} />
            <i aria-hidden="true" />
          </label>
          <label className="einst-schalter">
            <span>Breite Leiste mit Beschriftung</span>
            <input type="checkbox" checked={breit} onChange={aufBreite} />
            <i aria-hidden="true" />
          </label>
          <p className="einst-hinweis">
            Bewegung richtet sich nach dem System: Wer dort „Bewegung reduzieren“ eingestellt hat, sieht hier keine
            Animationen.
          </p>
        </section>

        <section className="einst-teil" style={{ "--i": 2 } as React.CSSProperties}>
          <h3>Tastenkürzel</h3>
          <dl className="einst-tasten">
            {TASTEN.map(([taste, was]) => (
              <div key={taste}>
                <dt>
                  {taste.split(" ").map((t) => (
                    <kbd key={t}>{t}</kbd>
                  ))}
                </dt>
                <dd>{was}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section className="einst-teil" style={{ "--i": 3 } as React.CSSProperties}>
          <h3>Modell</h3>
          <p className="einst-zeile">
            {SYSTEM.modell} · {zahl(SYSTEM.kontext)} Token Kontext · rund {SYSTEM.schreibenTs} Token/s
          </p>
        </section>

        <section className="einst-teil" style={{ "--i": 4 } as React.CSSProperties}>
          <h3>CLI (OpenCode)</h3>
          <CliZugang darf={nutzer.is_pro || nutzer.is_admin} />
        </section>

        <footer className="einst-fuss">
          <a className="knopf-still" href="/auth/logout">
            Abmelden
          </a>
          <span className="einst-recht">
            <a href={QUELLTEXT} target="_blank" rel="noopener noreferrer">
              GitHub
            </a>
            <a href="/impressum">Impressum</a>
            <a href="/datenschutz">Datenschutz</a>
            {/* Löschung auf Anfrage — wie, steht in der Datenschutzerklärung (Abschnitt „Deine Rechte“) */}
            <a href="/datenschutz">Konto löschen</a>
          </span>
        </footer>
      </aside>
    </div>
  );
}
