/* Einstiegspunkt.
 *
 * Die Schriften kommen als npm-Paket mit und werden mitgebündelt. Kein
 * `link rel=stylesheet` auf Google — sonst zeigt die Seite ohne Internet
 * eine Ersatzschrift, und bei DNS-Problemen im eigenen Netz gar nichts.
 *
 * Nur der lateinische Schnitt. Der volle Satz bringt Kyrillisch, Griechisch
 * und Vietnamesisch mit — 30 Dateien statt 10, für Zeichen, die hier nicht
 * vorkommen.
 */

import "@fontsource/ibm-plex-mono/latin-400.css";
import "@fontsource/ibm-plex-mono/latin-500.css";
import "@fontsource/ibm-plex-sans/latin-400.css";
import "@fontsource/ibm-plex-sans/latin-500.css";
import "@fontsource/ibm-plex-sans/latin-600.css";

import "./stil/marken.css";
import "./stil/grund.css";
import "./stil/knoepfe.css";
import "./stil/bewegung.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { RueckmeldungsAnbieter } from "./bausteine/Rueckmeldung";

const wurzel = document.getElementById("wurzel");
if (!wurzel) throw new Error("Kein Element mit der Kennung 'wurzel'");

createRoot(wurzel).render(
  <StrictMode>
    <RueckmeldungsAnbieter>
      <App />
    </RueckmeldungsAnbieter>
  </StrictMode>,
);
