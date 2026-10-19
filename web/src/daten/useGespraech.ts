/** Ein laufendes Gespräch.
 *
 * Der ganze Zustand an einer Stelle. Im alten Frontend lag er in elf
 * `useState` nebeneinander, und beim Abbrechen blieb regelmäßig eines davon
 * stehen — dann zeigte die Oberfläche „schreibt…", während längst nichts mehr
 * kam.
 *
 * Hier gibt es einen Reducer: jede Änderung ist ein benanntes Ereignis, und
 * der Abbruch räumt alles zugleich auf.
 */

import { useCallback, useEffect, useReducer, useRef } from "react";
import { type Anhang, nachrichtenInhalt } from "./anhaenge";
import { api } from "./api";
import { type StromEmpfaenger, type Stromende, stromLesen, stromWiederaufnehmen } from "./strom";
import type { Auftrag, Kontext, Nachricht, Stromereignis, Werkzeugaufruf } from "./typen";

/** Wendet `f` auf die Schritte des Auftrags `lauf` an. */
function imAuftrag(auftraege: Auftrag[], lauf: string, f: (a: Auftrag) => Auftrag): Auftrag[] {
  return auftraege.map((a) => (a.lauf === lauf ? f(a) : a));
}

/** Grobe Schätzung wie im Backend (kontext.py): ~3 Zeichen je Token.
 *  Das Fenster kommt vom Server (/api/modellstatus → fensterSetzen) — seit
 *  2026-10-16 nicht mehr fest 64k. */
let KONTEXT_MAX = 65536;
export function fensterSetzen(n: unknown): void {
  if (typeof n === "number" && n >= 8192) KONTEXT_MAX = n;
}
function kontextSchaetzen(nachrichten: Nachricht[]): Kontext | null {
  if (nachrichten.length === 0) return null;
  const belegt = Math.round(nachrichten.reduce((s, n) => s + n.content.length, 0) / 3) + 4000;
  const anteil = belegt / KONTEXT_MAX;
  return { belegt, max: KONTEXT_MAX, stufe: anteil >= 0.85 ? "voll" : anteil >= 0.75 ? "lang" : "ok" };
}

/** Name ohne den Zufallspräfix, den der Server beim Hochladen davorsetzt. */
export function dokumentName(gespeichert: string): string {
  return gespeichert.replace(/^[0-9a-f]{8,}_/, "");
}

/** Text einer Nachricht fürs Backend. Dokumente aus früheren Fragen gehen
 *  nicht noch einmal ganz mit — nur ihr Name, damit das Modell sie bei
 *  Bedarf mit read_document wieder lesen kann. Vorher waren sie nach der
 *  ersten Antwort für das Modell einfach weg. */
function fuersBackend(n: Nachricht): string {
  if (n.role !== "user" || !n.dokumente?.length) return n.content;
  return n.content + "\n\n" + n.dokumente.map((d) => `[Dokument-Datei: ${d}]`).join("\n");
}

interface Zustand {
  nachrichten: Nachricht[];
  /** Was gerade hereinkommt, noch nicht in `nachrichten`. */
  laufend: string;
  /** Denkweg der laufenden Antwort (Denkmodus). */
  gedanken: string;
  denkBeginn: number | null;
  denkEnde: number | null;
  werkzeuge: Werkzeugaufruf[];
  /** Laufende/fertige Agent-Aufträge der aktuellen Antwort. */
  auftraege: Auftrag[];
  agent: { id: string; name: string } | null;
  status: string | null;
  laeuft: boolean;
  fehler: string | null;
  sitzungId: number | null;
  anfrageId: string | null;
  /** Wie voll das Gesprächsfenster ist — vom Server nach jeder Antwort. */
  kontext: Kontext | null;
  /** Verbindung abgerissen, es wird neu verbunden. Eigenes Feld statt
   *  `status`: der Status verschwindet, sobald Text da ist — der Hinweis
   *  muss aber gerade dann sichtbar sein. */
  getrennt: boolean;
}

type Ereignis =
  | { art: "gestartet"; frage: Nachricht }
  /** Wieder angehängt: der Server schickt die laufende Antwort von vorn. */
  | { art: "wiederaufnahme" }
  | { art: "getrennt" }
  | { art: "text"; stueck: string }
  | { art: "strom"; ereignis: Stromereignis }
  | { art: "sitzung"; id: number; anfrageId?: string }
  | { art: "freigabe"; freigabeId: string; erlaubt: boolean }
  | { art: "beendet" }
  | { art: "fehler"; text: string }
  | { art: "geladen"; nachrichten: Nachricht[]; sitzungId: number | null }
  | { art: "gekuerzt"; behalten: number }
  | { art: "geleert" };

const LEER: Zustand = {
  nachrichten: [],
  laufend: "",
  gedanken: "",
  denkBeginn: null,
  denkEnde: null,
  werkzeuge: [],
  auftraege: [],
  agent: null,
  status: null,
  laeuft: false,
  fehler: null,
  sitzungId: null,
  anfrageId: null,
  kontext: null,
  getrennt: false,
};

function reduzieren(z: Zustand, e: Ereignis): Zustand {
  switch (e.art) {
    case "gestartet":
      return {
        ...z,
        nachrichten: [...z.nachrichten, e.frage],
        laufend: "",
        gedanken: "",
        denkBeginn: null,
        denkEnde: null,
        werkzeuge: [],
        auftraege: [],
        agent: null,
        status: null,
        laeuft: true,
        fehler: null,
      };

    case "wiederaufnahme":
      return {
        ...z,
        laufend: "",
        gedanken: "",
        denkBeginn: null,
        denkEnde: null,
        werkzeuge: [],
        auftraege: [],
        agent: null,
        status: null,
        laeuft: true,
        fehler: null,
        getrennt: false,
      };

    case "getrennt":
      return { ...z, getrennt: true };

    case "text":
      // Das erste Stück Antwort beendet das Denken.
      return {
        ...z,
        laufend: z.laufend + e.stueck,
        status: null,
        denkEnde: z.denkBeginn && !z.denkEnde ? Date.now() : z.denkEnde,
      };

    case "sitzung":
      return { ...z, sitzungId: e.id, anfrageId: e.anfrageId ?? z.anfrageId };

    case "strom": {
      const er = e.ereignis;
      if (!("type" in er)) return z;

      switch (er.type) {
        case "status":
          if (er.lauf) return { ...z, auftraege: imAuftrag(z.auftraege, er.lauf, (a) => ({ ...a, status: er.status })) };
          return { ...z, status: er.status };

        case "auftrag_start":
          return {
            ...z,
            status: null,
            auftraege: [
              ...z.auftraege,
              {
                lauf: er.lauf,
                kennung: er.kennung,
                name: er.name,
                auftrag: er.auftrag,
                farbe: er.color,
                zustand: "laeuft",
                schritte: [],
                beginn: Date.now(),
              },
            ],
          };

        case "auftrag_fertig":
          return {
            ...z,
            auftraege: imAuftrag(z.auftraege, er.lauf, (a) => ({
              ...a,
              zustand: er.ok ? "fertig" : "fehler",
              zusammenfassung: er.zusammenfassung,
              status: undefined,
              ende: Date.now(),
            })),
          };

        case "denken":
          return {
            ...z,
            gedanken: z.gedanken + er.text,
            denkBeginn: z.denkBeginn ?? Date.now(),
          };

        case "denken_ende":
          return { ...z, gedanken: z.gedanken + `\n\n— Nachdenken beendet: ${er.grund} —` };

        case "agent_selected":
          return { ...z, agent: { id: er.agent_id, name: er.agent_name } };

        case "tool_call":
          if (er.lauf)
            return {
              ...z,
              auftraege: imAuftrag(z.auftraege, er.lauf, (a) => ({
                ...a,
                status: undefined,
                schritte: [...a.schritte, { id: er.id, name: er.name, args: er.args, stufe: er.level, zustand: "laeuft" }],
              })),
            };
          return {
            ...z,
            status: null,
            werkzeuge: [
              ...z.werkzeuge,
              { id: er.id, name: er.name, args: er.args, stufe: er.level, zustand: "laeuft" },
            ],
          };

        case "approval_required":
          if (er.lauf)
            return {
              ...z,
              auftraege: imAuftrag(z.auftraege, er.lauf, (a) => ({
                ...a,
                schritte: [
                  ...a.schritte.filter((w) => w.id !== er.id),
                  { id: er.id, name: er.name, args: er.args, stufe: er.level, zustand: "wartet", freigabe_id: er.action_id },
                ],
              })),
            };
          return {
            ...z,
            status: null,
            werkzeuge: [
              ...z.werkzeuge.filter((w) => w.id !== er.id),
              {
                id: er.id,
                name: er.name,
                args: er.args,
                stufe: er.level,
                zustand: "wartet",
                freigabe_id: er.action_id,
              },
            ],
          };

        case "tool_result":
          if (er.lauf) {
            const lauf = er.lauf;
            return {
              ...z,
              auftraege: imAuftrag(z.auftraege, lauf, (a) => ({
                ...a,
                schritte: a.schritte.map((w) =>
                  w.id === er.id
                    ? { ...w, zustand: er.denied ? "abgelehnt" : "fertig", ergebnis: er.output, erfolg: er.success }
                    : w,
                ),
              })),
            };
          }
          return {
            ...z,
            werkzeuge: z.werkzeuge.map((w) =>
              w.id === er.id
                ? {
                    ...w,
                    zustand: er.denied ? "abgelehnt" : "fertig",
                    ergebnis: er.output,
                    erfolg: er.success,
                  }
                : w,
            ),
          };

        case "kontext":
          return { ...z, kontext: { belegt: er.belegt, max: er.max, stufe: er.stufe } };

        case "ersetzen":
          return { ...z, laufend: er.content };

        case "error":
          return { ...z, fehler: er.message, laeuft: false };

        default:
          return z;
      }
    }

    case "freigabe":
      // Sofort umstellen, ohne auf den Server zu warten. Ein Knopf, der nach
      // dem Druck noch eine Sekunde lang „warten" anzeigt, wird zweimal
      // gedrückt.
      const freigeben = (w: Werkzeugaufruf): Werkzeugaufruf =>
        w.freigabe_id === e.freigabeId
          ? { ...w, zustand: e.erlaubt ? "laeuft" : "abgelehnt", freigabe_id: undefined }
          : w;
      return {
        ...z,
        werkzeuge: z.werkzeuge.map(freigeben),
        auftraege: z.auftraege.map((a) => ({ ...a, schritte: a.schritte.map(freigeben) })),
      };

    case "beendet": {
      // Der laufende Text wird zur Nachricht. Ist nichts angekommen und auch
      // kein Werkzeug gelaufen, bleibt die Liste unverändert — eine leere
      // Antwortblase ist verwirrender als gar keine.
      const hatInhalt = z.laufend.trim().length > 0;
      return {
        ...z,
        nachrichten: hatInhalt
          ? [
              ...z.nachrichten,
              {
                role: "assistant",
                content: z.laufend,
                still: true,
                gedanken: z.gedanken || undefined,
                denkSekunden: z.denkBeginn
                  ? Math.max(1, Math.round(((z.denkEnde ?? Date.now()) - z.denkBeginn) / 1000))
                  : undefined,
                auftraege: z.auftraege.length ? z.auftraege : undefined,
                werkzeuge: z.werkzeuge.length ? z.werkzeuge : undefined,
              },
            ]
          : z.nachrichten,
        laufend: "",
        gedanken: "",
        denkBeginn: null,
        denkEnde: null,
        auftraege: hatInhalt ? [] : z.auftraege,
        werkzeuge: hatInhalt ? [] : z.werkzeuge,
        laeuft: false,
        status: null,
        anfrageId: null,
        getrennt: false,
      };
    }

    case "fehler":
      return { ...z, fehler: e.text, laeuft: false, status: null, getrennt: false };

    case "geladen":
      return { ...LEER, nachrichten: e.nachrichten, sitzungId: e.sitzungId, kontext: kontextSchaetzen(e.nachrichten) };

    case "gekuerzt":
      return { ...z, nachrichten: z.nachrichten.slice(0, e.behalten), fehler: null };

    case "geleert":
      return { ...LEER };
  }
}

/** Nach einem Abriss: erst schnell, dann alle 3 s neu verbinden — höchstens
 *  so kurz, damit Xera gleich weiterschreibt, wenn das Netz wieder da ist. */
const NEU_VERBINDEN_WARTEN = [300, 700, 1000, 2000];
const NEU_VERBINDEN_TAKT = 3000;
const NEU_VERBINDEN_MAX_MS = 120000;
/** Der Hinweis „Verbindung unterbrochen“ erst, wenn das Neuverbinden so lange
 *  nicht klappt — ein kurzer Aussetzer wird still überbrückt. */
const HINWEIS_NACH_MS = 5000;

/** `adresse`: das offene Gespräch steht in der Adresse (`/app/chat/493`),
 *  damit Neuladen es wieder öffnet. Cowork hat eigene Vorhaben und lässt das. */
export function useGespraech(optionen: { adresse?: boolean } = {}) {
  const [zustand, senden] = useReducer(reduzieren, LEER);
  const abbruchRef = useRef<AbortController | null>(null);
  // Wer gerade in den Zustand schreiben darf. Jeder Strom (Frage, Anhängen)
  // zieht eine Nummer; Laden, Leeren und neue Ströme machen die alte
  // ungültig. Sonst schreibt ein abgebrochener Strom mit seinem „beendet“
  // noch in das Gespräch, das inzwischen offen ist.
  const besitzerRef = useRef(0);

  // Offenes Gespräch in die Adresse — erst nach der ersten Änderung, sonst
  // würde der Start die Nummer aus der Adresse löschen, bevor sie geladen ist.
  const ersterLaufRef = useRef(true);
  useEffect(() => {
    if (ersterLaufRef.current) {
      ersterLaufRef.current = false;
      return;
    }
    if (!optionen.adresse) return;
    const bereich = window.location.pathname.split("/")[2];
    if (!bereich) return;
    const ziel = `/app/${bereich}` + (zustand.sitzungId ? `/${zustand.sitzungId}` : "");
    if (window.location.pathname !== ziel) window.history.replaceState(null, "", ziel);
  }, [zustand.sitzungId, optionen.adresse]);

  /** Neu verbinden, bis die Antwort fertig ist oder es aufgegeben wird. */
  const weiterLesen = useCallback(
    async (sitzungId: number, s: (e: Ereignis) => void, signal: AbortSignal, empfaenger: StromEmpfaenger): Promise<void> => {
      let seit = Date.now();
      for (let versuch = 0; Date.now() - seit < NEU_VERBINDEN_MAX_MS; versuch++) {
        const warten = NEU_VERBINDEN_WARTEN[versuch] ?? NEU_VERBINDEN_TAKT;
        if (Date.now() - seit >= HINWEIS_NACH_MS) s({ art: "getrennt" });
        await new Promise((r) => setTimeout(r, warten));
        if (signal.aborted) return;
        let ende: Stromende;
        try {
          ende = await stromWiederaufnehmen(sitzungId, empfaenger, () => s({ art: "wiederaufnahme" }), signal);
        } catch (fehler) {
          if (fehler instanceof DOMException && fehler.name === "AbortError") return;
          continue; // Netz noch weg
        }
        if (ende === "fertig") return;
        if (ende === "abgerissen") {
          // War wieder verbunden und ist erneut abgerissen: neuer Aussetzer,
          // wieder erst still versuchen.
          seit = Date.now();
          versuch = -1;
          continue;
        }
        if (ende === "keiner") {
          // Inzwischen fertig geworden: die Antwort steht in der Datenbank.
          const nachrichten = await api.nachrichten(sitzungId);
          s({ art: "geladen", nachrichten, sitzungId });
          return;
        }
      }
      s({ art: "fehler", text: "Verbindung verloren. Die Antwort läuft auf dem Server weiter — lade das Gespräch später neu." });
    },
    [],
  );

  const fragen = useCallback(
    async (
      text: string,
      optionen: { modus: string; agentId?: string; projektId?: number; ablage?: string; denken?: boolean; aufwand?: string; websuche?: boolean },
      anhaenge: Anhang[] = [],
      /** Statt des aktuellen Verlaufs — nach dem Kürzen ist der Zustand im
       *  Abschluss dieser Funktion noch der alte. */
      basis?: Nachricht[],
    ) => {
      const fertige = anhaenge.filter((a) => !a.laedt && !a.fehler);
      const frage: Nachricht = {
        role: "user",
        content: text,
        bilder: fertige.filter((a) => a.art === "bild" && a.bild).map((a) => a.bild!),
        dokumente: fertige.filter((a) => a.art === "dokument").map((a) => a.gespeichert ?? a.name),
      };
      abbruchRef.current?.abort();
      const meins = ++besitzerRef.current;
      const s = (e: Ereignis) => {
        if (besitzerRef.current === meins) senden(e);
      };
      s({ art: "gestartet", frage });

      const abbruch = new AbortController();
      abbruchRef.current = abbruch;
      // Für neue Gespräche kommt die Nummer erst mit dem ersten Ereignis.
      let sitzung = zustand.sitzungId;

      // Der Verlauf für das Backend: alles Bisherige als Text, die neue Frage
      // mit ihren Anhängen. Ältere Bilder gehen nicht noch einmal mit — sie
      // kosten bei jeder Frage wieder Zeit, und das Backend hat sie ohnehin
      // nicht gespeichert.
      const verlauf = [
        ...(basis ?? zustand.nachrichten).map((n) => ({ role: n.role, content: fuersBackend(n) as unknown })),
        { role: "user", content: nachrichtenInhalt(text, fertige) },
      ];

      const empfaenger: StromEmpfaenger = {
        aufText: (stueck) => s({ art: "text", stueck }),
        aufEreignis: (ereignis) => s({ art: "strom", ereignis }),
        aufSitzung: (id, anfrageId) => {
          sitzung = id;
          s({ art: "sitzung", id, anfrageId });
        },
      };
      try {
        const ende = await stromLesen(
          {
            nachrichten: verlauf,
            sitzungId: zustand.sitzungId ?? undefined,
            modus: optionen.modus,
            agentId: optionen.agentId,
            projektId: optionen.projektId,
            ablage: optionen.ablage,
            denken: optionen.denken,
            aufwand: optionen.aufwand,
            websuche: optionen.websuche,
            signal: abbruch.signal,
          },
          empfaenger,
        );
        // Verbindung mittendrin weg: die Antwort läuft auf dem Server weiter
        // — wieder anhängen statt aufgeben.
        if (ende === "abgerissen" && sitzung && !abbruch.signal.aborted) {
          await weiterLesen(sitzung, s, abbruch.signal, empfaenger);
        }
      } catch (fehler) {
        // Ein Abbruch ist kein Fehler — der Nutzer wollte das.
        if (!(fehler instanceof DOMException && fehler.name === "AbortError")) {
          s({
            art: "fehler",
            text: fehler instanceof Error ? fehler.message : "Unbekannter Fehler",
          });
        }
      } finally {
        if (abbruchRef.current === abbruch) abbruchRef.current = null;
        s({ art: "beendet" });
      }
    },
    [zustand.nachrichten, zustand.sitzungId, weiterLesen],
  );

  /** „Jetzt antworten“: nur das Nachdenken beenden, die Antwort läuft weiter. */
  const jetztAntworten = useCallback(() => {
    if (zustand.anfrageId) void api.denkenBeenden(zustand.anfrageId).catch(() => {});
  }, [zustand.anfrageId]);

  const abbrechen = useCallback(() => {
    abbruchRef.current?.abort();
    // Dem Server auch Bescheid geben, sonst rechnet er weiter. Scheitert das,
    // ist es nicht schlimm genug für eine Meldung — die Verbindung ist ohnehin
    // schon zu.
    if (zustand.anfrageId) void api.abbrechen(zustand.anfrageId).catch(() => {});
  }, [zustand.anfrageId]);

  const freigeben = useCallback((freigabeId: string, erlaubt: boolean) => {
    senden({ art: "freigabe", freigabeId, erlaubt });
    void api.freigeben(freigabeId, erlaubt).catch(() => {});
  }, []);

  /** Lädt ein Gespräch. Läuft dort gerade eine Antwort (auch nach dem
   *  Neuladen der Seite), hängt es sich wieder an und schreibt live weiter. */
  const laden = useCallback(
    async (sitzungId: number) => {
      abbruchRef.current?.abort();
      const meins = ++besitzerRef.current;
      const s = (e: Ereignis) => {
        if (besitzerRef.current === meins) senden(e);
      };
      const nachrichten = await api.nachrichten(sitzungId);
      s({ art: "geladen", nachrichten, sitzungId });
      if (besitzerRef.current !== meins) return;

      const abbruch = new AbortController();
      abbruchRef.current = abbruch;
      const empfaenger: StromEmpfaenger = {
        aufText: (stueck) => s({ art: "text", stueck }),
        aufEreignis: (ereignis) => s({ art: "strom", ereignis }),
        aufSitzung: (id, anfrageId) => s({ art: "sitzung", id, anfrageId }),
      };
      let angehaengt = false;
      try {
        const ende = await stromWiederaufnehmen(
          sitzungId,
          empfaenger,
          () => {
            angehaengt = true;
            s({ art: "wiederaufnahme" });
          },
          abbruch.signal,
        );
        if (ende === "abgerissen" && !abbruch.signal.aborted) {
          await weiterLesen(sitzungId, s, abbruch.signal, empfaenger);
        } else if (ende === "keiner" && nachrichten.at(-1)?.role === "user") {
          // Gerade zwischen beiden Abfragen fertig geworden.
          s({ art: "geladen", nachrichten: await api.nachrichten(sitzungId), sitzungId });
        }
      } catch {
        // Anhängen ist ein Zusatz — das Gespräch selbst ist geladen.
      } finally {
        if (abbruchRef.current === abbruch) abbruchRef.current = null;
        if (angehaengt) s({ art: "beendet" });
      }
    },
    [weiterLesen],
  );

  /** Kürzt Anzeige und Datenbank auf die ersten `behalten` Nachrichten. */
  const kuerzen = useCallback(
    async (behalten: number) => {
      senden({ art: "gekuerzt", behalten });
      if (zustand.sitzungId) await api.sitzungKuerzen(zustand.sitzungId, behalten);
      return zustand.nachrichten.slice(0, behalten);
    },
    [zustand.sitzungId, zustand.nachrichten],
  );

  /** Kontextschutz: „Zusammenfassen und weiter". */
  const verdichten = useCallback(async () => {
    if (!zustand.sitzungId) return;
    const verlauf = zustand.nachrichten.map((n) => ({ role: n.role, content: fuersBackend(n) as unknown }));
    const k = await api.kontextVerdichten(zustand.sitzungId, verlauf);
    senden({ art: "strom", ereignis: { type: "kontext", ...k } });
  }, [zustand.sitzungId, zustand.nachrichten]);

  /** Kontextschutz: „Neuer Chat mit Übergabe" — lädt das neue Gespräch. */
  const uebergeben = useCallback(async () => {
    if (!zustand.sitzungId) return null;
    const verlauf = zustand.nachrichten.map((n) => ({ role: n.role, content: fuersBackend(n) as unknown }));
    const neu = await api.kontextUebergabe(zustand.sitzungId, verlauf);
    const nachrichten = await api.nachrichten(neu.sitzung_id);
    ++besitzerRef.current;
    senden({ art: "geladen", nachrichten, sitzungId: neu.sitzung_id });
    return neu;
  }, [zustand.sitzungId, zustand.nachrichten]);

  const leeren = useCallback(() => {
    abbruchRef.current?.abort();
    ++besitzerRef.current;
    senden({ art: "geleert" });
  }, []);

  return { ...zustand, fragen, abbrechen, jetztAntworten, freigeben, laden, leeren, kuerzen, verdichten, uebergeben };
}
