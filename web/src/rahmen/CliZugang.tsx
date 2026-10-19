/** Zugang für die Xera-CLI — ein Teil der Einstellungen.
 *
 * Seit 2026-10-17 ist die CLI kein eigenes Programm mehr, sondern OpenCode mit
 * Xera als Anbieter (docs/plan-cli-opencode-2026-10.md). Hier holt man sich
 * den Schlüssel und die Befehle zum Einrichten. Der Schlüssel steht nur einmal
 * da: Xera speichert nur seinen Hash und kann ihn nicht noch einmal zeigen.
 */

import { useEffect, useState } from "react";
import { Kopieren } from "../bausteine/Kopieren";
import { api, ApiFehler } from "../daten/api";
import { CLI_SCHRITTE } from "../daten/cli";
import type { CliSchluessel } from "../daten/typen";

function datum(text: string | null): string {
  if (!text) return "noch nie";
  const d = new Date(text.replace(" ", "T") + "Z");
  return Number.isNaN(d.getTime()) ? text : d.toLocaleString("de-CH", { dateStyle: "short", timeStyle: "short" });
}

export function CliZugang({ darf }: { darf: boolean }) {
  const [liste, setListe] = useState<CliSchluessel[] | null>(null);
  const [neu, setNeu] = useState<string | null>(null);
  const [fehler, setFehler] = useState<string | null>(null);
  const [laeuft, setLaeuft] = useState(false);
  const [frage, setFrage] = useState<number | null>(null);

  async function laden() {
    try {
      setListe(await api.cliSchluessel());
    } catch (e) {
      setFehler(e instanceof ApiFehler ? e.message : "Schlüssel konnten nicht geladen werden.");
    }
  }

  useEffect(() => {
    if (darf) void laden();
  }, [darf]);

  async function erzeugen() {
    setLaeuft(true);
    setFehler(null);
    try {
      const r = await api.cliSchluesselNeu("OpenCode");
      setNeu(r.schluessel);
      await laden();
    } catch (e) {
      setFehler(e instanceof ApiFehler ? e.message : "Kein Schlüssel erzeugt.");
    } finally {
      setLaeuft(false);
    }
  }

  async function widerrufen(id: number) {
    if (frage !== id) {
      setFrage(id);
      return;
    }
    setFrage(null);
    try {
      await api.cliSchluesselWiderrufen(id);
      await laden();
    } catch (e) {
      setFehler(e instanceof ApiFehler ? e.message : "Widerrufen ging nicht.");
    }
  }

  if (!darf) {
    return <p className="einst-zeile">Die CLI gibt es für Pro-Nutzer.</p>;
  }

  return (
    <div className="cli">
      <p className="einst-zeile">
        Xera im Terminal: OpenCode mit Xera als Modell. Dateien und Befehle laufen auf deinem Rechner, die Gespräche
        speichert nur OpenCode bei dir. Erreichbar von überall, nur mit deinem Schlüssel.{" "}
        <a className="verweis" href="/app/cli">
          So funktioniert’s
        </a>
      </p>

      {neu && (
        <div className="cli-neu" role="status">
          <strong>Dein neuer Schlüssel — nur jetzt sichtbar</strong>
          <div className="cli-zeile">
            <code>{neu}</code>
            <Kopieren text={neu} />
          </div>
        </div>
      )}

      {liste && liste.length > 0 && (
        <ul className="cli-liste">
          {liste.map((s) => (
            <li key={s.id}>
              <span>
                <code>{s.anfang}…</code> {s.name}
                <small>zuletzt benutzt: {datum(s.zuletzt)}</small>
              </span>
              <button type="button" className={frage === s.id ? "ist-frage" : ""} onClick={() => widerrufen(s.id)}>
                {frage === s.id ? "wirklich widerrufen?" : "widerrufen"}
              </button>
            </li>
          ))}
        </ul>
      )}

      <button type="button" className="knopf-voll cli-erzeugen" onClick={erzeugen} disabled={laeuft}>
        {laeuft ? "erzeugt …" : "Neuer Schlüssel"}
      </button>
      {fehler && <p className="einst-hinweis cli-fehler">{fehler}</p>}

      <ol className="cli-befehle">
        {CLI_SCHRITTE.map(({ was, befehl }) => (
          <li key={was}>
            <span>{was}</span>
            <div className="cli-zeile">
              <code>{befehl}</code>
              <Kopieren text={befehl} />
            </div>
          </li>
        ))}
      </ol>
      <p className="einst-hinweis">
        OpenCode zeigt auch Modelle anderer Anbieter (z. B. „opencode/…-free“) — wer eines davon wählt, schickt seinen
        Code an Dritte. Für Xera: Modell <code>xera/xera</code>.
      </p>
      <p className="einst-hinweis">
        Für Linux, macOS und WSL. Denkaufwand wie <code>/effort</code> im Web: Variante <code>niedrig</code>,{" "}
        <code>mittel</code>, <code>hoch</code> oder <code>max</code> — z. B. <code>opencode run -m xera/xera#hoch "…"</code>,
        im Terminal mit dem Varianten-Wechsel.
      </p>
    </div>
  );
}
