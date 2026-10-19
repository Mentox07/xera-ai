/** Cowork: ein Arbeitsbereich je Vorhaben.
 *
 * Der Unterschied zum Chat ist nicht die Oberfläche, sondern was das Modell
 * mitbekommt. Im Chat fängt jedes Gespräch bei null an; hier gehören Dateien,
 * Notizen und eine feste Anweisung zum Projekt und werden jedem Gespräch
 * darin vorangestellt.
 *
 * Deshalb steht das alles sichtbar in der Tafel rechts und ist nicht in
 * Einstellungen versteckt: Wer nicht sieht, was dem Modell mitgegeben wird,
 * kann sich seine Antworten nicht erklären.
 *
 * Oktober 2026: Dateien (Text wird herausgezogen und geht mit), frühere
 * Gespräche des Vorhabens, Notizen bearbeiten, Vorhaben umbenennen/löschen.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Kontextanzeige } from "../bausteine/Kontextanzeige";
import { Begruessung } from "../bausteine/Begruessung";
import { Eingabe } from "../bausteine/Eingabe";
import { Gespraechsflaeche } from "../bausteine/Gespraechsflaeche";
import { useRueckmeldung } from "../bausteine/Rueckmeldung";
import { Zeichen } from "../bausteine/Zeichen";
import { api } from "../daten/api";
import { useGespraech } from "../daten/useGespraech";
import type { Projekt, Projektdatei, Projektnotiz, Sitzung } from "../daten/typen";
// Die Spalte links benutzt die Klassen des Verlaufs. Seit Cowork verzögert
// geladen wird, kommt Verlauf.css nicht mehr über den Chat-Bereich mit.
import "../bausteine/Verlauf.css";
import "../bausteine/Gespraechskopf.css";
import "./Cowork.css";

type Tafel = "gespraeche" | "dateien" | "notizen" | "anweisung";
const TAFELN: { id: Tafel; name: string }[] = [
  { id: "gespraeche", name: "Gespräche" },
  { id: "dateien", name: "Dateien" },
  { id: "notizen", name: "Notizen" },
  { id: "anweisung", name: "Anweisung" },
];

/** SQLite liefert "2026-10-01 07:04:49" in UTC, ohne Zone. */
function datum(roh?: string): string {
  if (!roh) return "";
  const d = new Date(roh.includes("T") ? roh : roh.replace(" ", "T") + "Z");
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString("de-CH");
}

function groesse(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function Cowork() {
  const [projekte, setProjekte] = useState<Projekt[]>([]);
  const [geladen, setGeladen] = useState(false);
  const [offen, setOffen] = useState<Projekt | null>(null);
  const [tafel, setTafel] = useState<Tafel>("gespraeche");
  const [notizen, setNotizen] = useState<Projektnotiz[]>([]);
  const [dateien, setDateien] = useState<Projektdatei[]>([]);
  const [gespraeche, setGespraeche] = useState<Sitzung[]>([]);
  const [eingabe, setEingabe] = useState("");
  const [ladefehler, setLadefehler] = useState<string | null>(null);
  const g = useGespraech();
  const { melden, fragen } = useRueckmeldung();

  const projekteLaden = useCallback(async () => {
    try {
      setProjekte(await api.projekte());
      setLadefehler(null);
    } catch (fehler) {
      setLadefehler(fehler instanceof Error ? fehler.message : "Projekte nicht ladbar");
    } finally {
      setGeladen(true);
    }
  }, []);

  useEffect(() => {
    void projekteLaden();
  }, [projekteLaden]);

  const gespraecheLaden = useCallback(async (id: number) => {
    try {
      setGespraeche(await api.projektGespraeche(id));
    } catch {
      setGespraeche([]);
    }
  }, []);

  useEffect(() => {
    if (!offen) return;
    void api.projektNotizen(offen.id).then(setNotizen).catch(() => setNotizen([]));
    void api.projektDateien(offen.id).then(setDateien).catch(() => setDateien([]));
    void gespraecheLaden(offen.id);
    g.leeren();
    setEingabe("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [offen?.id]);

  // Nach einer Antwort: die Gesprächsliste auffrischen (neues Gespräch, Titel).
  useEffect(() => {
    if (!g.laeuft && g.sitzungId && offen) void gespraecheLaden(offen.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [g.laeuft]);

  async function anlegen() {
    const name = await fragen({
      titel: "Neues Vorhaben",
      text: "Ein Name, unter dem du es wiederfindest.",
      eingabe: { platzhalter: "z. B. Umzug ins neue Rack" },
      bestaetigen: "Anlegen",
    });
    if (typeof name !== "string") return;
    try {
      const neu = await api.projektAnlegen({ name });
      setProjekte((p) => [neu, ...p]);
      setOffen(neu);
      setTafel("anweisung");
      melden(`„${neu.name}“ angelegt — trag rechts ein, worum es geht`, "gut");
    } catch (fehler) {
      melden(fehler instanceof Error ? fehler.message : "Anlegen fehlgeschlagen", "fehler");
    }
  }

  async function aendern(daten: Partial<Pick<Projekt, "name" | "beschreibung" | "anweisung">>): Promise<boolean> {
    if (!offen) return false;
    try {
      const gespeichert = await api.projektAendern(offen.id, daten);
      setOffen(gespeichert);
      setProjekte((p) => p.map((x) => (x.id === gespeichert.id ? gespeichert : x)));
      return true;
    } catch (fehler) {
      melden(fehler instanceof Error ? fehler.message : "Speichern fehlgeschlagen", "fehler");
      return false;
    }
  }

  async function umbenennen() {
    if (!offen) return;
    const name = await fragen({
      titel: "Vorhaben umbenennen",
      eingabe: { wert: offen.name },
      bestaetigen: "Umbenennen",
    });
    if (typeof name === "string" && name !== offen.name) await aendern({ name });
  }

  async function beschreiben() {
    if (!offen) return;
    const text = await fragen({
      titel: "Kurzbeschreibung",
      text: "Ein Satz, der auf der Karte in der Übersicht steht und dem Modell mitgegeben wird.",
      eingabe: { wert: offen.beschreibung, platzhalter: "Worum geht es?" },
      bestaetigen: "Speichern",
    });
    if (typeof text === "string") await aendern({ beschreibung: text });
  }

  async function vorhabenLoeschen() {
    if (!offen) return;
    const ja = await fragen({
      titel: "Vorhaben löschen?",
      text: `„${offen.name}“ mit allen Notizen und Dateien wird entfernt. Die Gespräche bleiben im Chat-Verlauf erhalten.`,
      bestaetigen: "Löschen",
      gefaehrlich: true,
    });
    if (!ja) return;
    try {
      await api.projektLoeschen(offen.id);
      setProjekte((p) => p.filter((x) => x.id !== offen.id));
      melden(`„${offen.name}“ gelöscht`, "gut");
      setOffen(null);
    } catch (fehler) {
      melden(fehler instanceof Error ? fehler.message : "Löschen fehlgeschlagen", "fehler");
    }
  }

  async function senden(direkt?: string) {
    const text = (direkt ?? eingabe).trim();
    if (!text || g.laeuft || !offen) return;
    setEingabe("");
    await g.fragen(text, { modus: "agents", projektId: offen.id, ablage: "cowork" });
  }

  /* --- Ohne Projekt: Übersicht ------------------------------------------- */

  if (!offen) {
    return (
      <main className="haupt cowork-uebersicht">
        <div className="cowork-mitte">
          <div className="cowork-kopfzeile">
            <div>
              <h1>Cowork</h1>
              <p className="cowork-unter">
                Ein Ort je Vorhaben. Dateien, Notizen und eine feste Anweisung gehören zum Projekt — jedes
                Gespräch darin kennt sie, ohne dass du sie wiederholst.
              </p>
            </div>
            <button type="button" className="knopf-betont" onClick={() => void anlegen()}>
              <Zeichen name="neu" groesse={14} />
              Neues Vorhaben
            </button>
          </div>

          {ladefehler ? (
            <p className="cowork-fehler">
              <Zeichen name="warnung" groesse={14} />
              {ladefehler}
            </p>
          ) : !geladen ? (
            <ul className="cowork-gitter">
              {[0, 1, 2].map((i) => (
                <li key={i}>
                  <span className="skelett cowork-skelett" />
                </li>
              ))}
            </ul>
          ) : projekte.length === 0 ? (
            <div className="cowork-start">
              <Zeichen name="cowork" groesse={28} />
              <p>
                Noch kein Vorhaben. Lohnt sich, sobald du zum selben Thema mehrmals fragst — etwa „Umzug ins
                neue Rack“ oder „Steuer 2026“.
              </p>
              <button type="button" className="knopf-betont" onClick={() => void anlegen()}>
                Erstes Vorhaben anlegen
              </button>
            </div>
          ) : (
            <ul className="cowork-gitter">
              {projekte.map((p, i) => (
                <li key={p.id} style={{ "--i": i } as React.CSSProperties}>
                  <button type="button" onClick={() => setOffen(p)}>
                    <span className="cowork-karte-name">{p.name}</span>
                    {p.beschreibung && <span className="cowork-karte-text">{p.beschreibung}</span>}
                    <span className="cowork-karte-fuss zahlen">
                      <span>
                        <Zeichen name="chat" groesse={12} /> {p.anzahl_gespraeche ?? 0}
                      </span>
                      <span>
                        <Zeichen name="notiz" groesse={12} /> {p.anzahl_dateien ?? 0}
                      </span>
                      <Zeichen name="pfeil-rechts" groesse={12} />
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </main>
    );
  }

  /* --- Im Projekt --------------------------------------------------------- */

  const tafelIndex = TAFELN.findIndex((t) => t.id === tafel);

  return (
    <>
      <aside className="cowork-spalte" aria-label="Vorhaben">
        <div className="verlauf-kopf">
          <span className="marke">Vorhaben</span>
          <button type="button" onClick={() => void anlegen()} title="Neues Vorhaben">
            <Zeichen name="neu" groesse={15} />
          </button>
        </div>
        <ul className="cowork-liste">
          {projekte.map((p, i) => (
            <li key={p.id}>
              <button
                type="button"
                style={{ "--i": i } as React.CSSProperties}
                className={"verlauf-eintrag" + (offen.id === p.id ? " ist-aktiv" : "")}
                onClick={() => setOffen(p)}
              >
                <span className="verlauf-titel">{p.name}</span>
              </button>
            </li>
          ))}
        </ul>
        <button type="button" className="cowork-zurueck" onClick={() => setOffen(null)}>
          <Zeichen name="pfeil-rechts" groesse={12} />
          Alle Vorhaben
        </button>
      </aside>

      <main className="haupt">
        <header className="cowork-kopf">
          <div className="cowork-kopf-text">
            <button type="button" className="cowork-titel" onClick={() => void umbenennen()} title="Umbenennen">
              <h2 key={offen.name}>{offen.name}</h2>
              <Zeichen name="stift" groesse={12} />
            </button>
            <button type="button" className="cowork-beschreibung" onClick={() => void beschreiben()}>
              {offen.beschreibung || "Kurzbeschreibung hinzufügen…"}
            </button>
          </div>
          <div className="cowork-kopf-aktionen">
            <button type="button" className="gkopf-knopf" onClick={() => { g.leeren(); setEingabe(""); }} title="Neues Gespräch im Vorhaben">
              <Zeichen name="neu" groesse={15} />
            </button>
            <button type="button" className="gkopf-knopf ist-gefahr" onClick={() => void vorhabenLoeschen()} title="Vorhaben löschen">
              <Zeichen name="muell" groesse={15} />
            </button>
          </div>
        </header>

        <div className="cowork-teilung">
          <div className="cowork-gespraech">
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
              begruessung={
                <Begruessung
                  zeichen="cowork"
                  titel={offen.name}
                  text={
                    offen.anweisung || notizen.length || dateien.length
                      ? `Dieses Gespräch kennt ${[
                          offen.anweisung && "die Anweisung",
                          notizen.length && `${notizen.length} Notiz${notizen.length === 1 ? "" : "en"}`,
                          dateien.length && `${dateien.length} Datei${dateien.length === 1 ? "" : "en"}`,
                        ]
                          .filter(Boolean)
                          .join(", ")} — frag einfach.`
                      : "Noch nichts hinterlegt. Rechts eine Anweisung schreiben oder Dateien hineinlegen, dann kennt jedes Gespräch hier den Zusammenhang."
                  }
                  vorschlaege={
                    dateien.length
                      ? [
                          `Fass mir die Datei „${dateien[0]!.name}“ zusammen.`,
                          "Was sind die offenen Punkte in diesem Vorhaben?",
                        ].map((t) => ({ text: t, aufKlick: () => void senden(t) }))
                      : undefined
                  }
                />
              }
            />
            <Kontextanzeige
              kontext={g.kontext}
              laeuft={g.laeuft}
              aufVerdichten={g.verdichten}
              aufUebergabe={async () => {
                await g.uebergeben();
                void gespraecheLaden(offen.id);
              }}
            />
            <Eingabe
              wert={eingabe}
              aufAenderung={setEingabe}
              aufSenden={() => void senden()}
              aufAbbruch={g.abbrechen}
              laeuft={g.laeuft}
              platzhalter={`Frage zu „${offen.name}“…`}
              hinweis={
                <span className="eingabe-projekt">
                  <Zeichen name="cowork" groesse={12} />
                  {offen.name}
                </span>
              }
            />
          </div>

          <aside className="cowork-tafel" aria-label="Projektwissen">
            <div className="cowork-reiter" role="tablist" style={{ "--index": tafelIndex, "--anzahl": TAFELN.length } as React.CSSProperties}>
              <span className="cowork-reiter-zeiger" aria-hidden="true" />
              {TAFELN.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  role="tab"
                  aria-selected={tafel === t.id}
                  className={tafel === t.id ? "ist-aktiv" : ""}
                  onClick={() => setTafel(t.id)}
                >
                  {t.name}
                  {t.id === "dateien" && dateien.length > 0 && <small>{dateien.length}</small>}
                  {t.id === "notizen" && notizen.length > 0 && <small>{notizen.length}</small>}
                </button>
              ))}
            </div>

            {tafel === "anweisung" ? (
              <Anweisungstafel key="anweisung" wert={offen.anweisung ?? ""} aufSpeichern={(w) => aendern({ anweisung: w })} />
            ) : tafel === "notizen" ? (
              <Notiztafel key="notizen" projektId={offen.id} notizen={notizen} aufAenderung={setNotizen} />
            ) : tafel === "dateien" ? (
              <Dateitafel key="dateien" projektId={offen.id} dateien={dateien} aufAenderung={setDateien} />
            ) : (
              <div className="cowork-inhalt" key="gespraeche">
                <p className="cowork-erklaerung">Frühere Gespräche in diesem Vorhaben. Klick öffnet es links.</p>
                {gespraeche.length === 0 ? (
                  <p className="cowork-leer-klein">Noch keine Gespräche.</p>
                ) : (
                  <ul className="cowork-gespraechsliste">
                    {gespraeche.map((s, i) => (
                      <li key={s.id} style={{ "--i": i } as React.CSSProperties}>
                        <button
                          type="button"
                          className={g.sitzungId === s.id ? "ist-aktiv" : undefined}
                          onClick={() => void g.laden(s.id).catch(() => melden("Gespräch nicht ladbar", "fehler"))}
                        >
                          <Zeichen name="chat" groesse={13} />
                          <span>{s.title || "Ohne Titel"}</span>
                          <small>{datum(s.created_at)}</small>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </aside>
        </div>
      </main>
    </>
  );
}

/* ------------------------------------------------------------------------ */

function Anweisungstafel({ wert, aufSpeichern }: { wert: string; aufSpeichern: (wert: string) => Promise<boolean> }) {
  const [entwurf, setEntwurf] = useState(wert);
  const [gespeichert, setGespeichert] = useState(false);

  useEffect(() => {
    setEntwurf(wert);
  }, [wert]);

  const geaendert = entwurf !== wert;

  return (
    <div className="cowork-inhalt">
      <p className="cowork-erklaerung">
        Steht am Anfang jedes Gesprächs in diesem Vorhaben. Gut geeignet: worum es geht, was du schon
        entschieden hast, welche Namen und Zahlen gelten.
      </p>
      <textarea
        className="cowork-feld"
        value={entwurf}
        onChange={(e) => {
          setEntwurf(e.target.value);
          setGespeichert(false);
        }}
        placeholder="Zum Beispiel: Umzug der Server ins neue Rack. Vier Höheneinheiten frei, USV bleibt unten. Kein Ausfall über 30 Minuten."
        spellCheck={false}
      />
      <div className="cowork-fussleiste">
        {gespeichert && <span className="cowork-gespeichert">gespeichert</span>}
        <button
          type="button"
          className="knopf-betont"
          disabled={!geaendert}
          onClick={async () => {
            if (await aufSpeichern(entwurf)) setGespeichert(true);
          }}
        >
          Übernehmen
        </button>
      </div>
    </div>
  );
}

function Notiztafel({
  projektId,
  notizen,
  aufAenderung,
}: {
  projektId: number;
  notizen: Projektnotiz[];
  aufAenderung: (n: Projektnotiz[]) => void;
}) {
  const [titel, setTitel] = useState("");
  const [inhalt, setInhalt] = useState("");
  /** Notiz, die gerade bearbeitet wird (Felder oben sind dann ihre). */
  const [bearbeitet, setBearbeitet] = useState<number | null>(null);
  const { melden, fragen } = useRueckmeldung();

  async function speichern() {
    if (!titel.trim() && !inhalt.trim()) return;
    try {
      const neu = await api.notizSpeichern(projektId, {
        id: bearbeitet ?? undefined,
        titel: titel.trim() || "Ohne Titel",
        inhalt: inhalt.trim(),
      });
      aufAenderung(bearbeitet ? notizen.map((n) => (n.id === neu.id ? neu : n)) : [neu, ...notizen]);
      setTitel("");
      setInhalt("");
      setBearbeitet(null);
    } catch (fehler) {
      melden(fehler instanceof Error ? fehler.message : "Notiz nicht gespeichert", "fehler");
    }
  }

  async function loeschen(n: Projektnotiz) {
    const ja = await fragen({
      titel: "Notiz löschen?",
      text: `„${n.titel}“ wird entfernt. Das Modell sieht sie ab der nächsten Frage nicht mehr.`,
      bestaetigen: "Löschen",
      gefaehrlich: true,
    });
    if (!ja) return;
    try {
      await api.notizLoeschen(projektId, n.id);
      aufAenderung(notizen.filter((x) => x.id !== n.id));
      if (bearbeitet === n.id) {
        setBearbeitet(null);
        setTitel("");
        setInhalt("");
      }
    } catch (fehler) {
      melden(fehler instanceof Error ? fehler.message : "Löschen fehlgeschlagen", "fehler");
    }
  }

  return (
    <div className="cowork-inhalt">
      <p className="cowork-erklaerung">
        Notizen liest das Modell mit. Kurze Festlegungen taugen besser als lange Texte — was hier steht,
        kostet bei jeder Frage Platz im Kontext.
      </p>

      <div className={"notiz-neu" + (bearbeitet ? " ist-bearbeitung" : "")}>
        <input value={titel} onChange={(e) => setTitel(e.target.value)} placeholder="Titel" aria-label="Titel der Notiz" />
        <textarea
          value={inhalt}
          onChange={(e) => setInhalt(e.target.value)}
          placeholder="Inhalt"
          aria-label="Inhalt der Notiz"
          rows={bearbeitet ? 6 : 3}
        />
        <div className="notiz-knoepfe">
          {bearbeitet && (
            <button
              type="button"
              className="knopf-still"
              onClick={() => {
                setBearbeitet(null);
                setTitel("");
                setInhalt("");
              }}
            >
              Abbrechen
            </button>
          )}
          <button
            type="button"
            className={bearbeitet ? "knopf-betont" : "knopf-still"}
            onClick={() => void speichern()}
            disabled={!titel.trim() && !inhalt.trim()}
          >
            {bearbeitet ? "Änderung speichern" : "Notiz anlegen"}
          </button>
        </div>
      </div>

      {notizen.length === 0 ? (
        <p className="cowork-leer-klein">Noch keine Notizen.</p>
      ) : (
        <ul className="notiz-liste">
          {notizen.map((n, i) => (
            <li key={n.id} className={bearbeitet === n.id ? "ist-aktiv" : undefined} style={{ "--i": i } as React.CSSProperties}>
              <div className="notiz-kopf">
                <strong>{n.titel}</strong>
                <span>
                  <button
                    type="button"
                    onClick={() => {
                      setBearbeitet(n.id);
                      setTitel(n.titel);
                      setInhalt(n.inhalt);
                    }}
                    title="Bearbeiten"
                    aria-label={`Notiz „${n.titel}“ bearbeiten`}
                  >
                    <Zeichen name="stift" groesse={12} />
                  </button>
                  <button type="button" onClick={() => void loeschen(n)} title="Löschen" aria-label={`Notiz „${n.titel}“ löschen`}>
                    <Zeichen name="muell" groesse={12} />
                  </button>
                </span>
              </div>
              {n.inhalt && <p>{n.inhalt}</p>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Dateitafel({
  projektId,
  dateien,
  aufAenderung,
}: {
  projektId: number;
  dateien: Projektdatei[];
  aufAenderung: (d: Projektdatei[]) => void;
}) {
  const [laden, setLaden] = useState<string[]>([]);
  const [zieht, setZieht] = useState(false);
  const dateiRef = useRef<HTMLInputElement>(null);
  const { melden, fragen } = useRueckmeldung();

  async function hochladen(liste: File[]) {
    let aktuell = dateien;
    for (const datei of liste) {
      setLaden((l) => [...l, datei.name]);
      try {
        const neu = await api.projektDateiHochladen(projektId, datei);
        aktuell = [neu, ...aktuell];
        aufAenderung(aktuell);
      } catch (fehler) {
        melden(`${datei.name}: ${fehler instanceof Error ? fehler.message : "Hochladen fehlgeschlagen"}`, "fehler");
      } finally {
        setLaden((l) => l.filter((n) => n !== datei.name));
      }
    }
  }

  async function loeschen(d: Projektdatei) {
    const ja = await fragen({
      titel: "Datei entfernen?",
      text: `„${d.name}“ wird aus dem Vorhaben genommen. Das Modell sieht sie ab der nächsten Frage nicht mehr.`,
      bestaetigen: "Entfernen",
      gefaehrlich: true,
    });
    if (!ja) return;
    try {
      await api.projektDateiLoeschen(projektId, d.id);
      aufAenderung(dateien.filter((x) => x.id !== d.id));
    } catch (fehler) {
      melden(fehler instanceof Error ? fehler.message : "Entfernen fehlgeschlagen", "fehler");
    }
  }

  return (
    <div
      className={"cowork-inhalt" + (zieht ? " zieht" : "")}
      onDragOver={(e) => {
        if (e.dataTransfer.types.includes("Files")) {
          e.preventDefault();
          setZieht(true);
        }
      }}
      onDragLeave={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node)) setZieht(false);
      }}
      onDrop={(e) => {
        e.preventDefault();
        setZieht(false);
        void hochladen(Array.from(e.dataTransfer.files));
      }}
    >
      <p className="cowork-erklaerung">
        Der Text der Dateien geht in jedes Gespräch mit — PDF, Word, Excel, Text. Je Datei bis etwa 8 000
        Zeichen, zusammen bis 24 000.
      </p>

      <button type="button" className="datei-ablage" onClick={() => dateiRef.current?.click()}>
        <Zeichen name="anhang" groesse={20} />
        <strong>{zieht ? "Loslassen zum Hinzufügen" : "Dateien hineinziehen oder auswählen"}</strong>
      </button>
      <input
        ref={dateiRef}
        type="file"
        multiple
        hidden
        accept=".pdf,.docx,.xlsx,.xls,.pptx,.txt,.csv,.md,.json,.log,.yaml,.yml"
        onChange={(e) => {
          const liste = Array.from(e.target.files ?? []);
          e.target.value = "";
          if (liste.length) void hochladen(liste);
        }}
      />

      <ul className="datei-liste">
        {laden.map((n) => (
          <li key={"l-" + n} className="laedt">
            <span className="anhang-ring" aria-hidden="true" />
            <span className="datei-name">{n}</span>
            <small>wird gelesen…</small>
          </li>
        ))}
        {dateien.map((d, i) => (
          <li key={d.id} style={{ "--i": i } as React.CSSProperties}>
            <Zeichen name="notiz" groesse={15} />
            <span className="datei-name" title={d.name}>
              {d.name}
            </span>
            <small>{groesse(d.groesse)}</small>
            <button type="button" onClick={() => void loeschen(d)} aria-label={`${d.name} entfernen`} title="Entfernen">
              <Zeichen name="muell" groesse={12} />
            </button>
          </li>
        ))}
      </ul>
      {dateien.length === 0 && laden.length === 0 && <p className="cowork-leer-klein">Noch keine Dateien.</p>}
    </div>
  );
}
