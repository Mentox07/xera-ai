/** Die Zeichen der Oberfläche.
 *
 * Selbst gezeichnet, nicht aus einer Bibliothek. Zwölf Pfade wiegen weniger
 * als jedes Icon-Paket, und sie lassen sich auf dieselbe Strichstärke bringen —
 * gemischte Sätze sind der Grund, warum Leisten oft unruhig aussehen.
 *
 * Alle auf 24×24 mit 1.6 Strichstärke, damit sie nebeneinander gleich schwer
 * wirken. Emoji kommen nicht vor: sie sehen auf jedem System anders aus.
 */

import type { ReactElement } from "react";

interface Eigenschaften {
  name: ZeichenName;
  groesse?: number;
  className?: string;
}

export type ZeichenName =
  | "chat"
  | "cowork"
  | "code"
  | "homelab"
  | "befehl"
  | "senden"
  | "stop"
  | "neu"
  | "anhang"
  | "ordner"
  | "notiz"
  | "muell"
  | "pfeil-rechts"
  | "haken"
  | "kreuz"
  | "warnung"
  | "menu"
  | "web"
  | "kopieren"
  | "nochmal"
  | "stift"
  | "denken"
  | "export"
  | "suche"
  | "agent"
  | "einstellungen"
  | "leiste";

const PFADE: Record<ZeichenName, ReactElement> = {
  chat: <path d="M4 5h16v11H9l-5 4V5z" />,
  // Drei Blätter übereinander: ein Ort, an dem mehreres zusammenliegt.
  cowork: (
    <>
      <path d="M4 7h9l2 2h5v10H4V7z" />
      <path d="M7 4h8l1.5 1.5" />
    </>
  ),
  code: <path d="M9 7l-5 5 5 5M15 7l5 5-5 5" />,
  // Ein Gehäuse mit Einschüben.
  homelab: (
    <>
      <rect x="4" y="5" width="16" height="6" rx="1" />
      <rect x="4" y="14" width="16" height="6" rx="1" />
      <path d="M7.5 8h.01M7.5 17h.01" />
    </>
  ),
  befehl: <path d="M7 5a2 2 0 100 4h10a2 2 0 100-4M7 19a2 2 0 110-4h10a2 2 0 110 4" />,
  senden: <path d="M4 12h14M13 6l6 6-6 6" />,
  stop: <rect x="6" y="6" width="12" height="12" rx="1.5" />,
  neu: <path d="M12 5v14M5 12h14" />,
  anhang: <path d="M17 8l-7.5 7.5a2.5 2.5 0 003.5 3.5L20 11a4.5 4.5 0 00-6.5-6.5L6 12" />,
  ordner: <path d="M4 6h6l2 2h8v11H4V6z" />,
  notiz: (
    <>
      <path d="M6 4h8l4 4v12H6V4z" />
      <path d="M14 4v4h4" />
    </>
  ),
  muell: <path d="M5 7h14M10 7V5h4v2M7 7l1 13h8l1-13" />,
  "pfeil-rechts": <path d="M9 6l6 6-6 6" />,
  haken: <path d="M5 12.5l5 5L19 7" />,
  kreuz: <path d="M6 6l12 12M18 6L6 18" />,
  warnung: <path d="M12 4l9 16H3l9-16zM12 10v4M12 17h.01" />,
  menu: <path d="M4 7h16M4 12h16M4 17h16" />,
  // Ein Globus: Kreis, Äquator, zwei Meridiane.
  web: (
    <>
      <circle cx="12" cy="12" r="8" />
      <path d="M4 12h16M12 4c2.5 2.5 2.5 13.5 0 16M12 4c-2.5 2.5-2.5 13.5 0 16" />
    </>
  ),
  kopieren: (
    <>
      <rect x="8" y="8" width="11" height="11" rx="1.5" />
      <path d="M5 15V6a1 1 0 011-1h9" />
    </>
  ),
  nochmal: <path d="M19 12a7 7 0 11-2.05-4.95M19 4v4h-4" />,
  stift: <path d="M5 19l1-4L16 5l3 3L9 18l-4 1zM14 7l3 3" />,
  // Eine Glühbirne: Denken eingeschaltet.
  denken: <path d="M9 18h6M10 21h4M12 3a6 6 0 00-3.5 10.9c.6.4 1 1.1 1 1.9V16h5v-.2c0-.8.4-1.5 1-1.9A6 6 0 0012 3z" />,
  export: <path d="M12 4v11M7 10l5 5 5-5M5 19h14" />,
  suche: (
    <>
      <circle cx="11" cy="11" r="6" />
      <path d="M20 20l-4.5-4.5" />
    </>
  ),
  agent: (
    <>
      <rect x="5" y="8" width="14" height="11" rx="3" />
      <path d="M12 4v4M9.5 13h.01M14.5 13h.01M9.5 16h5" />
    </>
  ),
  einstellungen: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1" />
    </>
  ),
  leiste: (
    <>
      <rect x="4" y="5" width="16" height="14" rx="2" />
      <path d="M10 5v14" />
    </>
  ),
};

export function Zeichen({ name, groesse = 18, className }: Eigenschaften) {
  return (
    <svg
      width={groesse}
      height={groesse}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      {PFADE[name]}
    </svg>
  );
}
