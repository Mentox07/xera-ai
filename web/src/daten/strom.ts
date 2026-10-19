/** Den Antwortstrom lesen.
 *
 * Das Backend schickt Server-Sent Events. Der Teil sieht harmlos aus und ist
 * die häufigste Fehlerquelle im Frontend: Ein Ereignis kommt selten in einem
 * Stück an. `fetch` liefert Netzwerkpakete, keine Zeilen — mitten in
 * `data: {"content": "Hal` kann der Puffer enden.
 *
 * Wer das übersieht, bekommt eine Oberfläche, die bei kurzen Antworten
 * funktioniert und bei langen Zeichen verschluckt.
 */

import type { Stromereignis } from "./typen";

export interface StromAnfrage {
  nachrichten: { role: string; content: unknown }[];
  sitzungId?: number;
  modus: string;
  agentId?: string;
  projektId?: number;
  /** In welchem Bereich ein neues Gespräch gelistet wird. */
  ablage?: string;
  /** Denkmodus: langsamer, gründlicher, Denkweg kommt als Ereignis. */
  denken?: boolean;
  /** Denkaufwand (aus · niedrig · mittel · hoch · max), seit 2026-10-19. */
  aufwand?: string;
  /** Websuche erzwingen (sonst sucht das Modell nur, wenn es das für nötig hält). */
  websuche?: boolean;
  signal?: AbortSignal;
}

export interface StromEmpfaenger {
  /** Ein Stück Antworttext ist da. */
  aufText(stueck: string): void;
  /** Ein Ereignis, das kein Text ist. */
  aufEreignis(ereignis: Stromereignis): void;
  /** Der Server hat die Sitzungsnummer mitgeteilt (bei neuen Gesprächen). */
  aufSitzung(id: number, anfrageId?: string): void;
}

/** Liest den Strom, bis er endet oder abgebrochen wird.
 *
 * Wirft nur, wenn die Anfrage selbst scheitert. Fehler *im* Strom kommen als
 * Ereignis durch — der Server hat dann schon geantwortet, und die halbe
 * Antwort ist mehr wert als eine Ausnahme. Reißt die Verbindung ab, kommt
 * `"abgerissen"` zurück: die Antwort läuft auf dem Server weiter.
 */
export async function stromLesen(
  anfrage: StromAnfrage,
  empfaenger: StromEmpfaenger,
): Promise<Stromende> {
  const antwort = await fetch("/api/chat", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    signal: anfrage.signal,
    body: JSON.stringify({
      messages: anfrage.nachrichten,
      session_id: anfrage.sitzungId,
      mode: anfrage.modus,
      agent_id: anfrage.agentId,
      projekt_id: anfrage.projektId,
      ablage: anfrage.ablage,
      denken: anfrage.denken || undefined,
      aufwand: anfrage.aufwand || undefined,
      websuche: anfrage.websuche || undefined,
      // Das Modell entscheidet selbst, ob es einen Agent braucht
      // (backend/vermittler.py) — statt Stichwort-Orchestrator vorab.
      routing: "modell",
      platform: "web",
    }),
  });

  if (!antwort.ok) {
    let text = `HTTP ${antwort.status}`;
    try {
      const daten = await antwort.json();
      text = daten.detail ?? daten.error ?? text;
    } catch {
      /* kein JSON */
    }
    empfaenger.aufEreignis({ type: "error", message: text });
    return "fertig";
  }
  if (!antwort.body) {
    empfaenger.aufEreignis({ type: "error", message: "Antwort ohne Inhalt" });
    return "fertig";
  }

  return await ereignisseLesen(antwort.body, empfaenger);
}

/** Wieder an eine laufende Antwort anhängen (nach Neuladen oder wenn das Netz
 *  kurz weg war). Der Server schickt erst alles Bisherige, dann live weiter.
 *
 *  `"keiner"`: es läuft nichts (mehr) — die Antwort steht in der Datenbank.
 *  `aufStart` kommt, bevor das erste Ereignis verarbeitet wird: der Aufrufer
 *  verwirft dort, was er von dieser Antwort schon angezeigt hat. */
export async function stromWiederaufnehmen(
  sitzungId: number,
  empfaenger: StromEmpfaenger,
  aufStart: () => void,
  signal?: AbortSignal,
): Promise<Stromende> {
  const antwort = await fetch(`/api/sessions/${sitzungId}/strom`, { credentials: "include", signal });
  if (antwort.status === 204 || !antwort.ok || !antwort.body) return "keiner";
  aufStart();
  return await ereignisseLesen(antwort.body, empfaenger);
}

/** `"fertig"`: der Server hat das Ende gemeldet. `"abgerissen"`: die
 *  Verbindung ist mittendrin weg — die Antwort läuft auf dem Server weiter. */
export type Stromende = "fertig" | "abgerissen" | "keiner";

async function ereignisseLesen(
  koerper: ReadableStream<Uint8Array>,
  empfaenger: StromEmpfaenger,
): Promise<Stromende> {
  const leser = koerper.getReader();
  const dekoder = new TextDecoder();
  // Was am Ende eines Pakets übrig bleibt, wartet hier auf den Rest.
  let rest = "";
  let ende = false;
  const pruefen = (inhalt: string) => {
    if (inhalt === '{"type": "ende"}') ende = true;
    else verarbeiten(inhalt, empfaenger);
  };

  try {
    for (;;) {
      const { done, value } = await leser.read();
      if (done) break;

      rest += dekoder.decode(value, { stream: true });

      // Ereignisse sind durch Leerzeilen getrennt. Das letzte Stück bleibt
      // liegen: es ist erst vollständig, wenn die nächste Leerzeile kommt.
      const bloecke = rest.split("\n\n");
      rest = bloecke.pop() ?? "";

      for (const block of bloecke) {
        for (const zeile of block.split("\n")) {
          if (!zeile.startsWith("data: ")) continue;
          const inhalt = zeile.slice(6).trim();
          if (!inhalt || inhalt === "[DONE]") continue;
          pruefen(inhalt);
        }
      }
    }
    // Was nach dem letzten Paket noch im Puffer liegt.
    if (rest.startsWith("data: ")) {
      const inhalt = rest.slice(6).trim();
      if (inhalt && inhalt !== "[DONE]") pruefen(inhalt);
    }
  } catch (fehler) {
    // Abbruch durch den Nutzer weiterreichen; alles andere ist ein
    // Netzfehler mitten im Strom.
    if (fehler instanceof DOMException && fehler.name === "AbortError") throw fehler;
    return "abgerissen";
  } finally {
    leser.releaseLock();
  }
  return ende ? "fertig" : "abgerissen";
}

function verarbeiten(roh: string, empfaenger: StromEmpfaenger): void {
  let daten: Record<string, unknown>;
  try {
    daten = JSON.parse(roh);
  } catch {
    // Ein unlesbares Ereignis darf den Strom nicht abreißen — der Rest der
    // Antwort ist noch brauchbar.
    return;
  }

  if ("session_id" in daten) {
    const id = daten.session_id;
    if (typeof id === "number") {
      empfaenger.aufSitzung(id, daten.request_id as string | undefined);
    }
    // Manche Ereignisse tragen die Sitzung *und* Inhalt.
    if (!("content" in daten) && !("type" in daten)) return;
  }

  // Der einfache Chat schickt Inhalt ohne `type`, der Agentweg mit
  // `type: "content"`. Beides ist Text.
  const typ = daten.type as string | undefined;
  if ((typ === undefined || typ === "content") && typeof daten.content === "string") {
    if (daten.content) empfaenger.aufText(daten.content);
    return;
  }

  empfaenger.aufEreignis(daten as Stromereignis);
}
