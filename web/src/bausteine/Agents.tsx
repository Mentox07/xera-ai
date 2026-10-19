/** Agents: Übersicht und Auswahl.
 *
 * Normalerweise wählt der Orchestrator den passenden Agent selbst. Wer es
 * genauer weiss, legt ihn fest — über die Übersicht (alle Agents als Karten)
 * oder mit „@“ im Eingabefeld. Der gewählte Agent bleibt, bis man ihn
 * entfernt; er steht als Marke im Eingabefeld.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import type { Agent } from "../daten/typen";
import { Zeichen } from "./Zeichen";
import "./Agents.css";

/** Das Kürzel auf der Karte: zwei Buchstaben in der Farbe des Agents.
 *  Emoji aus dem Backend werden nicht gezeigt — sie sehen auf jedem System
 *  anders aus (ENTWURF.md). */
export function AgentZeichen({ agent, groesse = 30 }: { agent: Pick<Agent, "name" | "color">; groesse?: number }) {
  const kuerzel = agent.name
    .replace(/\b(Agent|Assistant)\b/gi, "")
    .trim()
    .split(/[\s_-]+/)
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  return (
    <span
      className="agent-zeichen"
      style={{ "--farbe": agent.color ?? "var(--akzent)", width: groesse, height: groesse } as React.CSSProperties}
      aria-hidden="true"
    >
      {kuerzel || "A"}
    </span>
  );
}

export function AgentUebersicht({
  agents,
  offen,
  aufWahl,
  aufSchliessen,
}: {
  agents: Agent[];
  offen: boolean;
  aufWahl: (a: Agent) => void;
  aufSchliessen: () => void;
}) {
  const [suche, setSuche] = useState("");
  const feldRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!offen) return;
    setSuche("");
    setTimeout(() => feldRef.current?.focus(), 50);
    const taste = (e: KeyboardEvent) => e.key === "Escape" && aufSchliessen();
    window.addEventListener("keydown", taste);
    return () => window.removeEventListener("keydown", taste);
  }, [offen, aufSchliessen]);

  const [gruppe, setGruppe] = useState<"neu" | "alt">("neu");
  // Reiter nur, wenn es beide Sorten gibt. Seit 2026-10-02 liefert die API
  // der neuen Oberfläche nur noch Neubau-Agents.
  const hatNeue = agents.some((a) => a.neubau) && agents.some((a) => !a.neubau);

  const treffer = useMemo(() => {
    const s = suche.trim().toLowerCase();
    const auswahl = hatNeue ? agents.filter((a) => (gruppe === "neu" ? a.neubau : !a.neubau)) : agents;
    const gefiltert = s
      ? auswahl.filter((a) => (a.name + " " + (a.description ?? "") + " " + (a.kategorie ?? "")).toLowerCase().includes(s))
      : auswahl;
    // Neue nach Kategorie, damit Verwandtes beieinander steht.
    return gruppe === "neu"
      ? [...gefiltert].sort((x, y) => (x.kategorie ?? "").localeCompare(y.kategorie ?? "") || x.name.localeCompare(y.name, "de"))
      : gefiltert;
  }, [agents, suche, gruppe, hatNeue]);

  if (!offen) return null;

  return (
    <div className="agents-grund" onMouseDown={(e) => e.target === e.currentTarget && aufSchliessen()}>
      <div className="agents" role="dialog" aria-modal="true" aria-label="Agents">
        <header className="agents-kopf">
          <div>
            <h2>Agents</h2>
            <p>Normalerweise arbeitet Xera selbst und gibt Aufträge an Agents ab, wenn es viel Arbeit oder ein Werkzeug braucht — mehrere gleichzeitig. Hier legst du einen fest, den Xera dann sicher beauftragt.</p>
          </div>
          <button type="button" className="agents-zu" onClick={aufSchliessen} aria-label="Schliessen">
            <Zeichen name="kreuz" groesse={14} />
          </button>
        </header>
        {hatNeue && (
          <div className="agents-gruppen" role="tablist">
            <button type="button" role="tab" aria-selected={gruppe === "neu"} className={gruppe === "neu" ? "ist-aktiv" : ""} onClick={() => setGruppe("neu")}>
              Neu <small>{agents.filter((a) => a.neubau).length}</small>
            </button>
            <button type="button" role="tab" aria-selected={gruppe === "alt"} className={gruppe === "alt" ? "ist-aktiv" : ""} onClick={() => setGruppe("alt")}>
              Bisher <small>{agents.filter((a) => !a.neubau).length}</small>
            </button>
            {gruppe === "neu" && <span className="agents-hinweis">Testbetrieb — werden nur gezielt gewählt, nie automatisch.</span>}
          </div>
        )}
        <div className="agents-suche">
          <Zeichen name="suche" groesse={15} />
          <input
            ref={feldRef}
            value={suche}
            onChange={(e) => setSuche(e.target.value)}
            placeholder={`${agents.length} Agents durchsuchen…`}
            spellCheck={false}
          />
        </div>
        <ul className="agents-gitter">
          {treffer.map((a, i) => (
            <li key={a.id} style={{ "--i": i } as React.CSSProperties}>
              <button type="button" onClick={() => aufWahl(a)} style={{ "--farbe": a.color } as React.CSSProperties}>
                <AgentZeichen agent={a} />
                <span className="agents-text">
                  <strong>{a.name}</strong>
                  <span>{a.description}</span>
                  {a.neubau && a.kategorie && <em className="agents-kategorie">{a.kategorie}</em>}
                </span>
                {a.scope === "homelab" && <span className="agents-marke">Homelab</span>}
              </button>
            </li>
          ))}
          {treffer.length === 0 && <li className="agents-leer">Kein Agent passt zu „{suche}“.</li>}
        </ul>
      </div>
    </div>
  );
}

/** Die Liste über dem Eingabefeld, sobald man „@“ tippt. */
export function AgentVorschlaege({
  agents,
  suche,
  gewaehlt,
  aufWahl,
}: {
  agents: Agent[];
  suche: string;
  gewaehlt: number;
  aufWahl: (a: Agent) => void;
}) {
  if (agents.length === 0) {
    return <div className="agent-vorschlaege"><p className="agents-leer">Kein Agent heisst so.</p></div>;
  }
  return (
    <div className="agent-vorschlaege" role="listbox" aria-label={`Agents zu „${suche}“`}>
      {agents.slice(0, 7).map((a, i) => (
        <button
          key={a.id}
          type="button"
          role="option"
          aria-selected={i === gewaehlt}
          className={i === gewaehlt ? "ist-gewaehlt" : undefined}
          style={{ "--i": i } as React.CSSProperties}
          onMouseDown={(e) => {
            e.preventDefault();
            aufWahl(a);
          }}
        >
          <AgentZeichen agent={a} groesse={22} />
          <strong>{a.name}</strong>
          {a.neubau && <small className="agent-neu">neu</small>}
          <span>{a.description}</span>
        </button>
      ))}
    </div>
  );
}
