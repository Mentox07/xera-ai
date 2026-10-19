/** Was auf dem Server läuft, an einer Stelle.
 *
 * Startseite, Über uns, Lernteil, Diagramme und Begrüßung zeigen diese
 * Zahlen. Bis Oktober 2026 standen sie an fünf Stellen einzeln im Text — nach
 * dem Modellwechsel am 30.09. waren alle fünf falsch, und keiner hat es
 * gemerkt. Wer hier etwas ändert, ändert es überall.
 *
 * Alle Werte sind gemessen, nicht aus Datenblättern. Wo gerundet wird, steht
 * es dabei.
 */

export const SYSTEM = {
  modell: "Qwen3.8-Flash-Next",
  quantisierung: "UD-Q2_K_XL",
  /** Parameter des eigentlichen Modells, in Milliarden. */
  parameterMrd: 125,
  /** Davon pro Stück tatsächlich gerechnet (Mixture of Experts). */
  aktivMrd: 6,
  /** Nachschlagetabelle für Wortfolgen, in Milliarden Zahlen. */
  tabelleMrd: 51,

  /** Größe unverändert (16 Bit), in GB. */
  groesseRohGb: 355,
  /** Größe nach Quantisierung, in GB. */
  groesseGb: 79,
  /** Davon auf den Grafikkarten. */
  aufKartenGb: 50,
  /** Davon im Arbeitsspeicher: die Nachschlagetabelle. */
  imRamGb: 29,
  /** Mittlere Bitzahl je Zahl nach der Rundung, gerundet. */
  bitsImSchnitt: "dreieinhalb",

  /** Kontextfenster je Gespräch in Token. Sechs Plätze teilen sich 196 608. */
  kontext: 131_072,
  /** Token je Sekunde beim Schreiben (mit Multi-Token-Vorhersage). Median im
   *  Betrieb 23–24, allein 25–33, Code schneller als Prosa. */
  schreibenTs: 25,
  /** Token je Sekunde beim Lesen der Frage, Median bis 50 000 Token. Darüber
   *  sinkt es auf rund 75. */
  lesenTs: 160,
  /** Sekunden bis ein Bild verstanden ist, typisch. */
  bildSek: 10,
  /** Minuten, um ein volles Kontextfenster einzulesen (gemessen: 117 000
   *  Token in 22–28 Minuten). */
  vollesFensterMin: 25,

  karten: 5,
  kartenWort: "fünf",
  kartenText: "3× Quadro P4000, 1× Quadro P5000, 1× RTX A5000",
  vramGb: 64,

  /** Aus dem Protokoll von llama-server, 16./17.10. (Betrieb und Abnahmetests). */
  gemessenAm: "17.10.2026",
} as const;

/** Zahl mit schmalem Tausendertrenner, wie im Deutschen üblich: 65 536. */
export function zahl(n: number): string {
  return n.toLocaleString("de-CH").replace(/[’']/g, " ");
}
