/** Was zwischen Oberfläche und Backend hin und her geht.
 *
 * Die Ereignisse im Antwortstrom sind der heikle Teil: Das Backend schickt
 * Server-Sent Events mit einem `type`-Feld, und jede Sorte trägt andere
 * Felder. Ohne Typen ist an der Empfangsstelle nicht zu sehen, was da
 * ankommen kann — und genau dort sass im alten Frontend die Fehlersuche.
 */

export type BereichsId = "chat" | "cowork" | "code" | "homelab";

export interface Nutzer {
  id: string;
  username: string;
  avatar: string | null;
  is_admin: boolean;
  is_pro: boolean;
  has_homelab?: boolean;
  prompt_count: number;
  prompts_remaining: number;
  limit: number;
  is_guest?: boolean;
}

export interface Sitzung {
  id: number;
  title: string;
  mode: string;
  folder: string | null;
  created_at?: string;
  updated_at?: string;
  projekt_id?: number | null;
}

export interface Nachricht {
  id?: number;
  role: "user" | "assistant" | "system";
  content: string;
  created_at?: string;
  /** Nur in der Oberfläche: mitgeschickte Bilder (data:-URLs) und Dokumente.
   *  Das Backend speichert nur den Text — nach dem Neuladen sind sie weg. */
  bilder?: string[];
  dokumente?: string[];
  /** Werkzeuge, die das Modell selbst benutzt hat. Seit 2026-10-15 speichert
   *  das Backend sie mit (backend/karten.py) und liefert sie beim Laden mit. */
  werkzeuge?: Werkzeugaufruf[];
  /** Agent-Aufträge, die zu dieser Antwort gehörten (ebenfalls gespeichert). */
  auftraege?: Auftrag[];
  /** Der Denkweg (Denkmodus) und wie lange er dauerte (ebenfalls gespeichert). */
  gedanken?: string;
  denkSekunden?: number;
  /** Nur in der Oberfläche: war schon sichtbar (als laufende Antwort) und
   *  soll beim Übergang in den Verlauf nicht noch einmal einblenden. */
  still?: boolean;
}

/** Wie eingreifend ein Werkzeug ist. Kommt vom Backend, bestimmt die Farbe
 *  und ob gefragt wird. */
export type Stufe = "READ" | "WRITE" | "ADMIN" | "BLOCKED";

export interface Werkzeugaufruf {
  id: string;
  name: string;
  args: Record<string, unknown>;
  stufe: Stufe;
  /** Solange offen, wartet der Server auf eine Antwort. */
  freigabe_id?: string;
  zustand: "laeuft" | "wartet" | "fertig" | "abgelehnt" | "gesperrt";
  ergebnis?: string;
  erfolg?: boolean;
}

/** Ein Ereignis aus dem Antwortstrom.
 *
 * Die Namen kommen so vom Backend und sind deshalb englisch — sie hier
 * einzudeutschen würde nur eine Übersetzungsschicht erzeugen, die beim
 * nächsten Backend-Feld wieder auseinanderläuft.
 */
export type Stromereignis =
  | { type: "content"; content: string }
  | { type: "status"; status: string; lauf?: string }
  | { type: "agent_selected"; agent_id: string; agent_name: string; agent_icon?: string; agent_color?: string }
  | { type: "tool_call"; id: string; name: string; args: Record<string, unknown>; level: Stufe; lauf?: string }
  | { type: "tool_result"; id: string; name: string; success: boolean; output: string; denied?: boolean; lauf?: string }
  | { type: "approval_required"; id: string; action_id: string; name: string; args: Record<string, unknown>; level: Stufe; lauf?: string }
  | { type: "auftrag_start"; lauf: string; kennung: string; name: string; auftrag: string; color?: string }
  | { type: "auftrag_fertig"; lauf: string; ok: boolean; zusammenfassung: string }
  | { type: "error"; message: string }
  | { type: "denken"; text: string }
  /** Xera hat das Nachdenken beendet (Code im Denken, Zeitgrenze, „Jetzt antworten“). */
  | { type: "denken_ende"; grund: string }
  /** Ganze Antwort ersetzen — nach einer automatischen Code-Korrektur
   *  (backend/codepruefung.py). */
  | { type: "ersetzen"; content: string }
  | ({ type: "kontext" } & Kontext)
  | { session_id: number | null; request_id?: string }
  | { content: string };

/** Ein Auftrag des Hauptmodells an einen Agent (backend/auftraege.py).
 *  Mehrere laufen gleichzeitig; das Ergebnis geht ans Modell, nicht an den
 *  Nutzer — hier ist es nur zum Nachsehen. */
export interface Auftrag {
  lauf: string;
  kennung: string;
  name: string;
  auftrag: string;
  farbe?: string;
  zustand: "laeuft" | "fertig" | "fehler";
  schritte: Werkzeugaufruf[];
  status?: string;
  zusammenfassung?: string;
  beginn: number;
  ende?: number;
}

/** Wie voll das Gesprächsfenster ist (backend/kontext.py). */
export interface Kontext {
  belegt: number;
  max: number;
  /** ok < 75 % ≤ lang < 85 % ≤ voll; verdichtet = Älteres ist zusammengefasst. */
  stufe: "ok" | "lang" | "voll" | "verdichtet";
}

export interface Agent {
  id: string;
  name: string;
  icon?: string;
  color?: string;
  description?: string;
  tools?: string[];
  tab?: "chat" | "homelab" | "both";
  scope?: "general" | "homelab";
  /** Aus dem Neubau (~/xera), im Testbetrieb. */
  neubau?: boolean;
  kategorie?: string;
}

/* --- Cowork: Arbeitsbereich je Vorhaben ---------------------------------- */

export interface Projekt {
  id: number;
  name: string;
  beschreibung: string;
  /** Wird jedem Gespräch im Projekt vorangestellt. */
  anweisung: string;
  erstellt_am: string;
  geaendert_am: string;
  anzahl_gespraeche?: number;
  anzahl_dateien?: number;
}

export interface Projektdatei {
  id: number;
  projekt_id: number;
  name: string;
  groesse: number;
  hochgeladen_am: string;
}

export interface Projektnotiz {
  id: number;
  projekt_id: number;
  titel: string;
  inhalt: string;
  geaendert_am: string;
}

/** Schlüssel für die CLI (OpenCode). `anfang` = die ersten Zeichen zum Wiedererkennen. */
export interface CliSchluessel {
  id: number;
  name: string;
  anfang: string;
  erstellt: string;
  zuletzt: string | null;
}
