/** Hinweis oben in der App: Das Update ist durch (2026-10-19).
 *
 * Bleibt, bis man ihn wegklickt; gemerkt wird das nur in diesem Browser. Für das
 * nächste grosse Update einen neuen SCHLUESSEL nehmen, dann erscheint er wieder.
 */

import { useState } from "react";
import { Zeichen } from "./Zeichen";
import "./UpdateHinweis.css";

const SCHLUESSEL = "xera-update-2026-10-19";

function gesehen(): boolean {
  try {
    return localStorage.getItem(SCHLUESSEL) === "1";
  } catch {
    return false;
  }
}

export function UpdateHinweis() {
  const [zu, setZu] = useState(gesehen);
  if (zu) return null;

  function schliessen() {
    try {
      localStorage.setItem(SCHLUESSEL, "1");
    } catch {
      /* ohne Speicher eben nur bis zum Neuladen */
    }
    setZu(true);
  }

  return (
    <div className="update-hinweis" role="status">
      <span className="update-punkt" aria-hidden="true" />
      <p>
        <strong>Update abgeschlossen.</strong> Xera ist auf dem neuen Stand: Code-Bereich mit OpenCode, Xera im
        Terminal (<a href="/app/cli">CLI</a>) und Denkaufwand mit <code>/effort</code>.
      </p>
      <button type="button" onClick={schliessen} aria-label="Hinweis schliessen">
        <Zeichen name="kreuz" groesse={14} />
      </button>
    </div>
  );
}
