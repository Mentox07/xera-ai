/** Die Xera-CLI an einer Stelle: Befehle zum Einrichten und Eckdaten.
 *
 * Die Einstellungen (rahmen/CliZugang.tsx) und die Seite „CLI“ (bereiche/Cli.tsx)
 * zeigen dieselben Befehle. Zwei Fassungen liefen sonst auseinander, sobald sich
 * ein Pfad ändert — wie 2026-10-19, als die Regeln (AGENTS.md) dazukamen.
 *
 * Seit 2026-10-17 ist die CLI kein eigenes Programm mehr, sondern OpenCode mit
 * Xera als Anbieter (docs/plan-cli-opencode-2026-10.md).
 */

export interface CliSchritt {
  /** Kurz, für die Seite „CLI“. */
  titel: string;
  /** Ausführlich, für die Einstellungen. */
  was: string;
  befehl: string;
}

// Schlüssel über `opencode auth login`, nicht als Umgebungsvariable: OpenCode 2
// schickt die Anfragen aus einem Hintergrunddienst, und der kennt Variablen
// aus der .bashrc nicht (2026-10-18: es kam nur „Schlüssel fehlt“).
export const CLI_SCHRITTE: CliSchritt[] = [
  {
    titel: "OpenCode installieren",
    was: "OpenCode installieren",
    befehl: "curl -fsSL https://opencode.ai/v2/install | bash",
  },
  {
    titel: "Xera eintragen",
    // Die Regeln als globale AGENTS.md: "instructions" in der Konfiguration lädt OpenCode 2.0.29
    // nicht (getestet 2026-10-19), AGENTS.md schon — gleiche Regeln wie im Web-Code-Bereich.
    was: "Xera eintragen: Konfiguration und Xera-Regeln (ersetzt eine vorhandene opencode.jsonc und globale AGENTS.md)",
    befehl:
      "mkdir -p ~/.config/opencode && cd ~/.config/opencode && curl -fsSL https://xera-app.com/cli/opencode.jsonc -o opencode.jsonc && curl -fsSL https://xera-app.com/cli/regeln.md -o AGENTS.md && cd -",
  },
  {
    titel: "Schlüssel hinterlegen",
    was: "Schlüssel hinterlegen — fragt nach dem Schlüssel, einfügen und Enter. Neuer Schlüssel: denselben Befehl nochmals (der gespeicherte gilt vor jeder Variable)",
    befehl: "opencode auth login xera",
  },
  {
    titel: "Im Projektordner starten",
    was: "Im Projektordner starten",
    befehl: "opencode",
  },
];

/** Die Varianten in opencode.jsonc — dieselben Stufen wie `/effort` im Web (daten/aufwand.ts). */
export const CLI_VARIANTEN = ["niedrig", "mittel", "hoch", "max"] as const;

/** Grenzen je Nutzer, wie sie das Backend durchsetzt (openai_api._Schutz, Startwerte 2026-10-19). */
export const CLI_GRENZEN = {
  proMinute: 60,
  proTag: 3000,
  tokensProTag: 3_000_000,
};

/** Was OpenCode bei jeder Anfrage mitschickt (Systemprompt, Werkzeuge, Xera-Regeln),
 *  gemessen 2026-10-19 an einer ersten Anfrage: 8 046 Token. */
export const CLI_GRUNDLAST_TOKEN = 8000;

export const OPENCODE = {
  repo: "https://github.com/anomalyco/opencode",
  repoName: "github.com/anomalyco/opencode",
  seite: "https://opencode.ai",
  doku: "https://opencode.ai/docs",
  lizenz: "MIT",
};
