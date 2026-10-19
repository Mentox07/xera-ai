/** Anbindung ans Backend.
 *
 * Eine Stelle für alle Aufrufe. Im alten Frontend standen `fetch`-Aufrufe
 * verstreut über 4 145 Zeilen, jeder mit eigener Fehlerbehandlung — und die
 * meisten ohne. Ein Aufruf, der still fehlschlägt, erzeugt eine Oberfläche,
 * die aussieht als lade sie noch.
 */

import type {
  Agent,
  CliSchluessel,
  Kontext,
  Nachricht,
  Nutzer,
  Projekt,
  Projektdatei,
  Projektnotiz,
  Sitzung,
} from "./typen";

export class ApiFehler extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly kennung?: string,
  ) {
    super(message);
    this.name = "ApiFehler";
  }
}

async function hole<T>(pfad: string, init?: RequestInit): Promise<T> {
  let antwort: Response;
  try {
    antwort = await fetch(pfad, {
      credentials: "include",
      ...init,
      headers: {
        ...(typeof init?.body === "string" ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch (fehler) {
    // Netz weg, Server weg, abgebrochen — für den Aufrufer dasselbe Problem,
    // aber es muss unterscheidbar von einem 500er bleiben.
    throw new ApiFehler(
      fehler instanceof Error && fehler.name === "AbortError"
        ? "Abgebrochen"
        : "Server nicht erreichbar",
      0,
    );
  }

  if (!antwort.ok) {
    let text = antwort.statusText;
    let kennung: string | undefined;
    try {
      const daten = await antwort.json();
      text = daten.detail ?? daten.error ?? text;
      kennung = daten.error;
    } catch {
      /* Antwort war kein JSON — dann bleibt der Statustext. */
    }
    throw new ApiFehler(text, antwort.status, kennung);
  }

  if (antwort.status === 204) return undefined as T;
  return antwort.json() as Promise<T>;
}

export const api = {
  /* --- Wer bin ich --------------------------------------------------- */
  ich: () => hole<Nutzer>("/api/me"),

  /* --- Gespräche ------------------------------------------------------ */
  sitzungen: (modus?: string) =>
    hole<Sitzung[]>("/api/sessions" + (modus ? `?mode=${encodeURIComponent(modus)}` : "")),

  nachrichten: (id: number) => hole<Nachricht[]>(`/api/sessions/${id}/messages`),

  sitzungAendern: (id: number, aenderung: { title?: string; folder?: string | null }) =>
    hole<{ ok: boolean }>(`/api/sessions/${id}`, {
      method: "PATCH",
      body: JSON.stringify(aenderung),
    }),

  /** Behält die ersten `behalten` Nachrichten, löscht den Rest — für „neu
   *  erzeugen“ und „bearbeiten“. */
  /** Kontextschutz: jetzt zusammenfassen bzw. neues Gespräch mit Übergabe. */
  kontextVerdichten: (sitzungId: number, nachrichten: { role: string; content: unknown }[]) =>
    hole<Kontext>("/api/kontext/verdichten", {
      method: "POST",
      body: JSON.stringify({ sitzung_id: sitzungId, nachrichten }),
    }),
  kontextUebergabe: (sitzungId: number, nachrichten: { role: string; content: unknown }[]) =>
    hole<{ sitzung_id: number; titel: string }>("/api/kontext/uebergabe", {
      method: "POST",
      body: JSON.stringify({ sitzung_id: sitzungId, nachrichten }),
    }),
  sitzungKuerzen: (id: number, behalten: number) =>
    hole<{ ok: boolean; geloescht: number }>(`/api/sessions/${id}/kuerzen`, {
      method: "POST",
      body: JSON.stringify({ behalten }),
    }),

  sitzungLoeschen: (id: number) =>
    hole<{ ok: boolean }>(`/api/sessions/${id}`, { method: "DELETE" }),

  ordner: (modus?: string) =>
    hole<string[]>("/api/folders" + (modus ? `?mode=${encodeURIComponent(modus)}` : "")),

  /* --- Dateien -------------------------------------------------------- */
  hochladen: (datei: File) => {
    const form = new FormData();
    form.append("file", datei);
    // Kein Content-Type setzen: Den richtigen mit Grenze setzt der Browser.
    return hole<{ name: string; content: string; type: string; stored_name: string }>("/api/upload", {
      method: "POST",
      body: form,
      headers: {},
    });
  },

  /* --- Agents --------------------------------------------------------- */
  /** Nur die Neubau-Agents (seit 2026-10-02 die einzigen in der neuen Oberfläche). */
  agents: (tab?: "chat" | "homelab") => hole<Agent[]>(`/api/agents?neu=1${tab ? `&tab=${tab}` : ""}`),

  /* --- Werkzeugfreigabe ----------------------------------------------- */
  freigeben: (freigabeId: string, erlaubt: boolean) =>
    hole<{ ok: boolean }>(`/api/approve/${freigabeId}`, {
      method: "POST",
      body: JSON.stringify({ approved: erlaubt }),
    }),

  /** „Jetzt antworten“ — beendet nur das Nachdenken (seit 2026-10-19). */
  denkenBeenden: (anfrageId: string) =>
    hole<{ ok: boolean }>("/api/denken-beenden", {
      method: "POST",
      body: JSON.stringify({ request_id: anfrageId }),
    }),

  abbrechen: (anfrageId: string) =>
    hole<{ ok: boolean }>("/api/stop", {
      method: "POST",
      body: JSON.stringify({ request_id: anfrageId }),
    }),

  /* --- Cowork: Projekte ----------------------------------------------- */
  projekte: () => hole<Projekt[]>("/api/projekte"),

  projekt: (id: number) => hole<Projekt>(`/api/projekte/${id}`),

  projektAnlegen: (daten: { name: string; beschreibung?: string; anweisung?: string }) =>
    hole<Projekt>("/api/projekte", { method: "POST", body: JSON.stringify(daten) }),

  projektAendern: (id: number, daten: Partial<Pick<Projekt, "name" | "beschreibung" | "anweisung">>) =>
    hole<Projekt>(`/api/projekte/${id}`, { method: "PATCH", body: JSON.stringify(daten) }),

  projektLoeschen: (id: number) =>
    hole<{ ok: boolean }>(`/api/projekte/${id}`, { method: "DELETE" }),

  projektDateien: (id: number) => hole<Projektdatei[]>(`/api/projekte/${id}/dateien`),

  projektDateiHochladen: (id: number, datei: File) => {
    const form = new FormData();
    form.append("file", datei);
    return hole<Projektdatei>(`/api/projekte/${id}/dateien`, { method: "POST", body: form });
  },

  projektDateiLoeschen: (id: number, dateiId: number) =>
    hole<{ ok: boolean }>(`/api/projekte/${id}/dateien/${dateiId}`, { method: "DELETE" }),

  projektGespraeche: (id: number) => hole<Sitzung[]>(`/api/projekte/${id}/gespraeche`),

  projektNotizen: (id: number) => hole<Projektnotiz[]>(`/api/projekte/${id}/notizen`),

  notizSpeichern: (projektId: number, notiz: { id?: number; titel: string; inhalt: string }) =>
    hole<Projektnotiz>(`/api/projekte/${projektId}/notizen`, {
      method: "POST",
      body: JSON.stringify(notiz),
    }),

  notizLoeschen: (projektId: number, notizId: number) =>
    hole<{ ok: boolean }>(`/api/projekte/${projektId}/notizen/${notizId}`, { method: "DELETE" }),

  /* --- CLI (OpenCode, seit 2026-10-17) -------------------------------- */
  cliSchluessel: () => hole<CliSchluessel[]>("/api/cli/schluessel"),

  /** Der Klartext steht nur in dieser Antwort — Xera speichert nur den Hash. */
  cliSchluesselNeu: (name: string) =>
    hole<CliSchluessel & { schluessel: string }>("/api/cli/schluessel", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),

  cliSchluesselWiderrufen: (id: number) =>
    hole<{ ok: boolean }>(`/api/cli/schluessel/${id}`, { method: "DELETE" }),
};
