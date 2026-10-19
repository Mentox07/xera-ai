/** Chat, Code und Homelab teilen sich diesen Bereich.
 *
 * Was sie unterscheidet, sind drei Dinge: der Modus, den das Backend bekommt,
 * die Begrüssung und — bei Homelab — der Hinweis, dass hier Werkzeuge laufen,
 * die etwas anfassen. Alles andere ist gleich, und das gehört auch gleich
 * gebaut.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Zeichen } from "../bausteine/Zeichen";
import { AgentUebersicht, AgentVorschlaege, AgentZeichen } from "../bausteine/Agents";
import { Kontextanzeige } from "../bausteine/Kontextanzeige";
import { Eingabe } from "../bausteine/Eingabe";
import { Gespraechskopf } from "../bausteine/Gespraechskopf";
import { useRueckmeldung } from "../bausteine/Rueckmeldung";
import { Gespraechsflaeche } from "../bausteine/Gespraechsflaeche";
import { Verlauf } from "../bausteine/Verlauf";
import { type Anhang, anhaengeVerarbeiten } from "../daten/anhaenge";
import { type Aufwand, STUFEN, aufwandBefehl, aufwandLaden, aufwandName, aufwandSpeichern } from "../daten/aufwand";
import { AufwandWahl } from "../bausteine/AufwandWahl";
import { api } from "../daten/api";
import { useGespraech } from "../daten/useGespraech";
import type { Agent, Sitzung } from "../daten/typen";
import type { Bereich } from "../rahmen/bereiche";

interface Eigenschaften {
  bereich: Bereich;
  /** Bekommt eine Funktion, mit der ein Vorschlag direkt gefragt wird. */
  begruessung: (fragen: (text: string) => void) => React.ReactNode;
  platzhalter: string;
  /** Bei Cowork: das gewählte Projekt wird mitgeschickt. */
  projektId?: number;
  /** Von aussen (Befehlspalette): dieses Gespräch öffnen. `n` ändert sich bei
   *  jedem Auftrag, damit dasselbe Gespräch zweimal geöffnet werden kann. */
  oeffnen?: { id: number; n: number } | null;
  hinweis?: React.ReactNode;
}

export function Gespraechsbereich({
  bereich,
  begruessung,
  platzhalter,
  projektId,
  hinweis,
  oeffnen,
}: Eigenschaften) {
  const g = useGespraech({ adresse: true });
  const { melden, fragen } = useRueckmeldung();
  const [eingabe, setEingabe] = useState("");
  const [sitzungen, setSitzungen] = useState<Sitzung[]>([]);
  const [ladend, setLadend] = useState(true);
  const [gehend, setGehend] = useState<number | null>(null);
  const [anhaenge, setAnhaenge] = useState<Anhang[]>([]);
  const [zieht, setZieht] = useState(false);
  const ziehZaehler = useRef(0);
  // Websuche: nur im Chat. Schickt die Frage an den Web-Search-Agent.
  const [websuche, setWebsuche] = useState(false);
  const mitWebsuche = bereich.id === "chat" && websuche;
  const [verlaufOffen, setVerlaufOffen] = useState(false);
  // Denkaufwand (seit 2026-10-19, vorher „Gründlich denken“ an/aus): lässt sich
  // mit Agent und Websuche kombinieren, Agents denken gedeckelt mit. Bleibt
  // über das Neuladen hinweg gewählt.
  const [aufwand, setAufwandRoh] = useState<Aufwand>(aufwandLaden);
  const setAufwand = (a: Aufwand) => {
    setAufwandRoh(a);
    aufwandSpeichern(a);
  };
  const kannDenken = bereich.id !== "cowork";
  const mitDenken = kannDenken && aufwand !== "aus";

  // Agents: Liste für Übersicht und @-Vorschläge, und der festgelegte Agent.
  // Nicht im Chat (seit 2026-10-02): dort antwortet das Modell mit seinen
  // Grundwerkzeugen selbst. Nicht mehr im Code-Bereich (seit 2026-10-19): der
  // arbeitet mit OpenCode wie die CLI, mit dessen eigenen Unteragenten.
  // Xera-Agents gibt es in Cowork und Homelab.
  const mitAgents = bereich.id !== "chat" && bereich.id !== "code";
  const [agents, setAgents] = useState<Agent[]>([]);
  const [agent, setAgent] = useState<Agent | null>(null);
  const [agentsOffen, setAgentsOffen] = useState(false);
  const [vorschlagIndex, setVorschlagIndex] = useState(0);
  const [vorschlagZu, setVorschlagZu] = useState<string | null>(null);
  useEffect(() => {
    setAgent(null);
    if (!mitAgents) {
      setAgents([]);
      return;
    }
    api
      .agents(bereich.id === "homelab" ? "homelab" : "chat")
      .then(setAgents)
      .catch(() => setAgents([]));
  }, [bereich.id, mitAgents]);
  useEffect(() => {
    if (!mitAgents) return;
    const auf = () => setAgentsOffen(true);
    window.addEventListener("xera:agents", auf);
    return () => window.removeEventListener("xera:agents", auf);
  }, [mitAgents]);
  // „@code“ am Ende des Feldes öffnet die Vorschläge.
  const atTreffer = /(^|\s)@([\p{L}\p{N}_-]*)$/u.exec(eingabe);
  const atSuche = atTreffer ? atTreffer[2]!.toLowerCase() : null;
  const vorschlaege =
    !mitAgents || atSuche === null || vorschlagZu === eingabe
      ? null
      : agents.filter((a) => (a.name + " " + a.id).toLowerCase().includes(atSuche)).slice(0, 7);

  function agentWaehlen(a: Agent) {
    setAgent(a);
    setWebsuche(false);
    setAgentsOffen(false);
    setEingabe((t) => t.replace(/(^|\s)@[\p{L}\p{N}_-]*$/u, "$1"));
    setVorschlagIndex(0);
  }
  const aktuelleSitzung = sitzungen.find((x) => x.id === g.sitzungId) ?? null;

  const dateienAnnehmen = useCallback((dateien: File[]) => {
    anhaengeVerarbeiten(
      dateien,
      (a) => setAnhaenge((alt) => [...alt, a]),
      (a) => {
        setAnhaenge((alt) => alt.map((x) => (x.id === a.id ? a : x)));
        if (a.fehler) melden(`${a.name}: ${a.fehler}`, "fehler");
      },
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const listeLaden = useCallback(async () => {
    try {
      setSitzungen(await api.sitzungen(bereich.ablage));
      setLadend(false);
    } catch {
      setLadend(false);
      // Ohne Verlauf lässt sich weiterarbeiten — eine Fehlermeldung dafür
      // wäre lauter als der Schaden.
    }
  }, [bereich.ablage]);

  useEffect(() => {
    void listeLaden();
  }, [listeLaden]);

  // Beim Bereichswechsel das Gespräch zurücksetzen: eine Antwort aus dem
  // Chat im Homelab-Verlauf stehen zu lassen wäre irreführend.
  useEffect(() => {
    g.leeren();
    setEingabe("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bereich.id]);

  // Neuladen: das Gespräch aus der Adresse wieder öffnen (`/app/chat/493`).
  // Läuft dort noch eine Antwort, hängt `laden` sich an und schreibt weiter.
  useEffect(() => {
    const [, , teil, nummer] = window.location.pathname.split("/");
    const id = Number(nummer);
    if (teil !== bereich.id || !Number.isInteger(id) || id <= 0) return;
    void g.laden(id).catch(() => melden("Gespräch konnte nicht geladen werden", "fehler"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Nach dem Ende einer Antwort die Liste auffrischen — ein neues Gespräch
  // hat gerade einen Titel bekommen.
  useEffect(() => {
    if (!g.laeuft && g.sitzungId) void listeLaden();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [g.laeuft]);

  async function senden(direkt?: string) {
    const mitgeschickt = direkt ? [] : anhaenge;
    let text = (direkt ?? eingabe).trim();
    // „/effort hoch“ — wie in Claude Code: stellt den Denkaufwand, geht nicht ans Modell.
    const befehl = direkt ? null : aufwandBefehl(text);
    if (befehl) {
      setEingabe("");
      if (befehl === "liste" || befehl === "?") {
        melden(`Denkaufwand: ${STUFEN.map((s) => s.id).join(" · ")} — z. B. /effort hoch (jetzt: ${aufwandName(aufwand)})`, befehl === "?" ? "fehler" : "info");
      } else if (!kannDenken) {
        melden("In Cowork denkt Xera nicht vorab nach.", "info");
      } else {
        setAufwand(befehl);
        melden(`Denkaufwand: ${aufwandName(befehl)}`, "gut");
      }
      return;
    }
    if (g.laeuft || mitgeschickt.some((a) => a.laedt)) return;
    if (!text && mitgeschickt.length === 0) return;
    // Nur ein Anhang ohne Text: eine sinnvolle Frage daraus machen, statt
    // dem Modell eine leere Nachricht zu schicken.
    if (!text) text = mitgeschickt.some((a) => a.art === "bild") ? "Was ist auf dem Bild?" : "Fass das Dokument zusammen.";
    setEingabe("");
    setAnhaenge([]);
    await g.fragen(text, optionen(), mitgeschickt);
  }

  function optionen() {
    // Ein festgelegter Agent hat Vorrang. Sonst antwortet das Modell selbst
    // und sucht bei Bedarf direkt im Netz; der Schalter erzwingt die Suche.
    const agentId = agent?.id;
    return {
      modus: agentId ? (bereich.id === "homelab" ? "homelab" : "agents") : bereich.modus,
      agentId,
      projektId,
      ablage: bereich.ablage,
      denken: mitDenken || undefined,
      aufwand: mitDenken ? aufwand : undefined,
      websuche: (!agentId && mitWebsuche) || undefined,
    };
  }

  /** Die letzte Antwort verwerfen und dieselbe Frage noch einmal stellen. */
  async function neuErzeugen() {
    if (g.laeuft) return;
    const i = g.nachrichten.map((n) => n.role).lastIndexOf("user");
    if (i < 0) return;
    const frage = g.nachrichten[i]!;
    try {
      const basis = await g.kuerzen(i);
      await g.fragen(frage.content, optionen(), [], basis);
    } catch (fehler) {
      melden(fehler instanceof Error ? fehler.message : "Neu erzeugen fehlgeschlagen", "fehler");
    }
  }

  /** Eine Frage zurück ins Feld holen; alles ab dort wird verworfen. */
  async function bearbeiten(index: number) {
    if (g.laeuft) return;
    const frage = g.nachrichten[index];
    if (!frage) return;
    const ab = g.nachrichten.length - index;
    if (ab > 2) {
      const ja = await fragen({
        titel: "Ab hier neu fragen?",
        text: `Die Frage kommt zurück ins Eingabefeld. Die ${ab - 1} Nachrichten danach werden verworfen.`,
        bestaetigen: "Bearbeiten",
      });
      if (!ja) return;
    }
    try {
      await g.kuerzen(index);
      setEingabe(frage.content);
    } catch (fehler) {
      melden(fehler instanceof Error ? fehler.message : "Bearbeiten fehlgeschlagen", "fehler");
    }
  }

  useEffect(() => {
    if (!oeffnen) return;
    void g.laden(oeffnen.id).catch(() => melden("Gespräch konnte nicht geladen werden", "fehler"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [oeffnen?.n]);

  // Neues Gespräch: Strg Alt N. Strg N allein öffnet im Browser ein Fenster
  // und lässt sich nicht zuverlässig abfangen.
  useEffect(() => {
    function taste(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.altKey && e.key.toLowerCase() === "n") {
        e.preventDefault();
        neu();
      }
    }
    window.addEventListener("keydown", taste);
    return () => window.removeEventListener("keydown", taste);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function neu() {
    g.leeren();
    setEingabe("");
    setAnhaenge([]);
  }

  async function umbenennen(titel: string) {
    if (!g.sitzungId) return;
    try {
      await api.sitzungAendern(g.sitzungId, { title: titel });
      setSitzungen((alt) => alt.map((x) => (x.id === g.sitzungId ? { ...x, title: titel } : x)));
    } catch (fehler) {
      melden(fehler instanceof Error ? fehler.message : "Umbenennen fehlgeschlagen", "fehler");
    }
  }

  async function ordnen(sitzung: Sitzung) {
    let ordner: string | null = null;
    if (!sitzung.folder) {
      const vorhandene = [...new Set(sitzungen.map((x) => x.folder).filter(Boolean))] as string[];
      const antwort = await fragen({
        titel: "In einen Ordner legen",
        text: vorhandene.length
          ? `Vorhandene Ordner: ${vorhandene.join(", ")}. Ein neuer Name legt einen neuen an.`
          : "Ein Name für den Ordner. Er erscheint oben im Verlauf.",
        eingabe: { platzhalter: "z. B. Schule, Homelab, Bewerbung" },
        bestaetigen: "Ablegen",
      });
      if (typeof antwort !== "string") return;
      ordner = antwort;
    }
    try {
      await api.sitzungAendern(sitzung.id, { folder: ordner ?? "" });
      setSitzungen((alt) => alt.map((x) => (x.id === sitzung.id ? { ...x, folder: ordner } : x)));
      melden(ordner ? `In „${ordner}“ abgelegt` : `Aus „${sitzung.folder}“ genommen`, "gut");
    } catch (fehler) {
      melden(fehler instanceof Error ? fehler.message : "Verschieben fehlgeschlagen", "fehler");
    }
  }

  function exportieren() {
    const titel = aktuelleSitzung?.title || "Gespräch";
    const zeilen = [`# ${titel}`, "", `_Xera · ${bereich.name} · ${new Date().toLocaleString("de-CH")}_`, ""];
    for (const n of g.nachrichten) {
      zeilen.push(n.role === "user" ? "## Frage" : "## Antwort", "", n.content, "");
    }
    const blob = new Blob([zeilen.join("\n")], { type: "text/markdown;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${titel.replace(/[^\p{L}\p{N} _-]/gu, "").trim().slice(0, 60) || "gespraech"}.md`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    melden("Als Markdown gesichert", "gut");
  }

  async function loeschen(id: number) {
    const titel = sitzungen.find((s) => s.id === id)?.title || "Ohne Titel";
    const ja = await fragen({
      titel: "Gespräch löschen?",
      text: `„${titel}“ und alle Nachrichten darin werden entfernt.`,
      bestaetigen: "Löschen",
      gefaehrlich: true,
    });
    if (!ja) return;
    try {
      await api.sitzungLoeschen(id);
      if (g.sitzungId === id) g.leeren();
      // Erst zuklappen lassen, dann neu laden — sonst verschwindet die Zeile
      // ohne dass man sieht, welche es war.
      setGehend(id);
      setTimeout(() => {
        setGehend(null);
        void listeLaden();
      }, 300);
    } catch (fehler) {
      melden(fehler instanceof Error ? fehler.message : "Löschen fehlgeschlagen", "fehler");
    }
  }

  // Esc bricht ab. Nur wenn gerade etwas läuft, sonst schluckt es die Taste
  // vor anderen Bedienelementen weg.
  useEffect(() => {
    if (!g.laeuft) return;
    function taste(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        g.abbrechen();
      }
    }
    window.addEventListener("keydown", taste);
    return () => window.removeEventListener("keydown", taste);
  }, [g.laeuft, g]);

  return (
    <>
      <Verlauf
        titel={bereich.name}
        sitzungen={sitzungen}
        aktiv={g.sitzungId}
        aufWaehlen={(id) => {
          setVerlaufOffen(false);
          void g.laden(id).catch(() => melden("Gespräch konnte nicht geladen werden", "fehler"));
        }}
        aufNeu={() => {
          setVerlaufOffen(false);
          neu();
        }}
        aufOrdner={(s) => void ordnen(s)}
        offen={verlaufOffen}
        aufSchliessen={() => setVerlaufOffen(false)}
        aufLoeschen={(id) => void loeschen(id)}
        ladend={ladend}
        gehend={gehend}
      />

      <main
        className={"haupt" + (zieht ? " zieht" : "")}
        onDragEnter={(e) => {
          if (!e.dataTransfer.types.includes("Files")) return;
          e.preventDefault();
          ziehZaehler.current += 1;
          setZieht(true);
        }}
        onDragOver={(e) => {
          if (e.dataTransfer.types.includes("Files")) e.preventDefault();
        }}
        onDragLeave={() => {
          // dragleave feuert auch beim Wechsel auf ein Kind-Element — erst
          // wenn alle verlassen sind, ist man wirklich draussen.
          ziehZaehler.current = Math.max(0, ziehZaehler.current - 1);
          if (ziehZaehler.current === 0) setZieht(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          ziehZaehler.current = 0;
          setZieht(false);
          const dateien = Array.from(e.dataTransfer.files);
          if (dateien.length) dateienAnnehmen(dateien);
        }}
      >
        <Gespraechskopf
          bereichName={bereich.name}
          titel={aktuelleSitzung?.title ?? null}
          hatSitzung={Boolean(g.sitzungId)}
          hatNachrichten={g.nachrichten.length > 0}
          agent={g.agent?.name ?? null}
          websuche={mitWebsuche}
          denken={mitDenken ? aufwandName(aufwand) : undefined}
          aufUmbenennen={(t) => void umbenennen(t)}
          aufExport={exportieren}
          aufLoeschen={() => g.sitzungId && void loeschen(g.sitzungId)}
          aufNeu={neu}
          aufVerlauf={() => setVerlaufOffen(true)}
        />
        <AgentUebersicht
          agents={agents}
          offen={agentsOffen}
          aufWahl={agentWaehlen}
          aufSchliessen={() => setAgentsOffen(false)}
        />
        {zieht && (
          <div className="ablage" aria-hidden="true">
            <div className="ablage-kasten">
              <Zeichen name="anhang" groesse={28} />
              <strong>Loslassen zum Anhängen</strong>
              <span>Bilder, PDF, Word, Excel, Text</span>
            </div>
          </div>
        )}
        <Gespraechsflaeche
          nachrichten={g.nachrichten}
          laufend={g.laufend}
          werkzeuge={g.werkzeuge}
          auftraege={g.auftraege}
          agent={g.agent}
          status={g.status}
          getrennt={g.getrennt}
          laeuft={g.laeuft}
          fehler={g.fehler}
          aufFreigabe={g.freigeben}
          aufNeuErzeugen={() => void neuErzeugen()}
          gedanken={g.gedanken}
          denkBeginn={g.denkBeginn}
          aufJetztAntworten={g.jetztAntworten}
          aufBearbeiten={(i) => void bearbeiten(i)}
          begruessung={begruessung((text) => void senden(text))}
        />
        <Kontextanzeige
          kontext={g.kontext}
          laeuft={g.laeuft}
          aufVerdichten={g.verdichten}
          aufUebergabe={async () => {
            await g.uebergeben();
            void listeLaden();
          }}
        />
        <Eingabe
          wert={eingabe}
          aufAenderung={setEingabe}
          aufSenden={() => void senden()}
          aufAbbruch={g.abbrechen}
          laeuft={g.laeuft}
          platzhalter={mitWebsuche ? "Im Web suchen…" : mitDenken ? "Schwierige Frage? Hier wird gründlich nachgedacht…" : platzhalter}
          hinweis={hinweis}
          anhaenge={anhaenge}
          vorsatz={
            agent ? (
              <span className="agent-gewaehlt" style={{ "--farbe": agent.color ?? "var(--akzent)" } as React.CSSProperties}>
                <AgentZeichen agent={agent} groesse={20} />
                <strong>{agent.name}</strong>
                <button type="button" onClick={() => setAgent(null)} aria-label={`${agent.name} entfernen`}>
                  <Zeichen name="kreuz" groesse={10} />
                </button>
              </span>
            ) : undefined
          }
          ueber={
            vorschlaege ? (
              <AgentVorschlaege
                agents={vorschlaege}
                suche={atSuche ?? ""}
                gewaehlt={Math.min(vorschlagIndex, Math.max(0, vorschlaege.length - 1))}
                aufWahl={agentWaehlen}
              />
            ) : undefined
          }
          aufTaste={(e) => {
            if (!vorschlaege || vorschlaege.length === 0) return false;
            if (e.key === "ArrowDown" || e.key === "ArrowUp") {
              e.preventDefault();
              const n = vorschlaege.length;
              setVorschlagIndex((i) => (e.key === "ArrowDown" ? (i + 1) % n : (i - 1 + n) % n));
              return true;
            }
            if (e.key === "Enter" || e.key === "Tab") {
              e.preventDefault();
              agentWaehlen(vorschlaege[Math.min(vorschlagIndex, vorschlaege.length - 1)]!);
              return true;
            }
            if (e.key === "Escape") {
              e.preventDefault();
              setVorschlagZu(eingabe);
              return true;
            }
            return false;
          }}
          aufDateien={dateienAnnehmen}
          aufAnhangWeg={(id) => setAnhaenge((alt) => alt.filter((a) => a.id !== id))}
          schalter={
            <>
              {bereich.id === "chat" && (
                <button
                  type="button"
                  className={"eingabe-werkzeug" + (websuche ? " ist-an" : "")}
                  onClick={() => {
                    setWebsuche((w) => !w);
                    setAgent(null);
                  }}
                  aria-pressed={websuche}
                  title={websuche ? "Websuche ist an — Xera sucht bei jeder Frage im Netz, mit Quellen" : "Websuche erzwingen (sonst entscheidet Xera selbst, ob es sucht)"}
                >
                  <Zeichen name="web" groesse={16} />
                </button>
              )}
              {agents.length > 0 && (
                <button
                  type="button"
                  className={"eingabe-werkzeug" + (agent ? " ist-an" : "")}
                  onClick={() => setAgentsOffen(true)}
                  title="Agent festlegen (oder @ tippen)"
                >
                  <Zeichen name="agent" groesse={16} />
                </button>
              )}
              {kannDenken && <AufwandWahl wert={aufwand} aufWahl={setAufwand} />}
            </>
          }
        />
      </main>
    </>
  );
}
