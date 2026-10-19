/** Die Vorführung auf der Startseite.
 *
 * Ersetzt das Standbild der Oberfläche. Ein Bild zeigt, wie es aussieht; das
 * hier zeigt, wie es sich anfühlt: Die Frage wird getippt, steigt auf, das
 * Modell denkt kurz nach, und die Antwort baut sich Zeile für Zeile auf —
 * so, wie sie auch wirklich entsteht.
 *
 * Kein Video, keine Bilddatei: dieselben Bausteine und Klassen wie die echte
 * Oberfläche, nur mit vorgegebenem Text. Wer „Bewegung reduzieren“
 * eingestellt hat, sieht gleich den fertigen Zustand.
 */

import { useEffect, useState } from "react";
import { bewegungAus } from "../stil/bewegung";
import { Marke } from "./Marke";
import { Zeichen } from "./Zeichen";
import "./Vorfuehrung.css";

const FRAGE = "Erklär mir kurz TCP und UDP, mit einer Tabelle.";
const ZEILEN: [string, string, string][] = [
  ["Verbindung", "fester Aufbau (Handshake)", "keiner, einfach senden"],
  ["Zuverlässigkeit", "garantiert, in Reihenfolge", "ohne Garantie"],
  ["Tempo", "etwas langsamer", "schnell, wenig Aufwand"],
  ["Typisch für", "Web, E-Mail, Downloads", "Streaming, VoIP, Spiele"],
];
const SCHLUSS =
  "TCP nimmst du, wenn nichts verloren gehen darf. UDP, wenn Tempo wichtiger ist als jedes einzelne Paket.";
const VERLAUF = ["TCP und UDP im Vergleich", "Backup-Skript für das NAS", "Warum bricht die VPN ab?", "Docker Compose aufteilen"];

type Schritt = "tippt" | "denkt" | "schreibt" | "steht";

export function Vorfuehrung() {
  const ruhig = bewegungAus();
  const [schritt, setSchritt] = useState<Schritt>(ruhig ? "steht" : "tippt");
  const [getippt, setGetippt] = useState(ruhig ? FRAGE.length : 0);
  const [zeilen, setZeilen] = useState(ruhig ? ZEILEN.length : 0);
  const [schluss, setSchluss] = useState(ruhig ? SCHLUSS.length : 0);
  const [runde, setRunde] = useState(0);

  useEffect(() => {
    if (ruhig) return;
    let t: ReturnType<typeof setTimeout>;
    if (schritt === "tippt") {
      if (getippt < FRAGE.length) t = setTimeout(() => setGetippt((n) => n + 1), 38 + Math.random() * 40);
      else t = setTimeout(() => setSchritt("denkt"), 500);
    } else if (schritt === "denkt") {
      t = setTimeout(() => setSchritt("schreibt"), 1500);
    } else if (schritt === "schreibt") {
      if (zeilen < ZEILEN.length) t = setTimeout(() => setZeilen((n) => n + 1), 420);
      else if (schluss < SCHLUSS.length) t = setTimeout(() => setSchluss((n) => Math.min(SCHLUSS.length, n + 3)), 28);
      else t = setTimeout(() => setSchritt("steht"), 200);
    } else {
      // Stehen lassen, dann von vorn.
      t = setTimeout(() => {
        setGetippt(0);
        setZeilen(0);
        setSchluss(0);
        setRunde((r) => r + 1);
        setSchritt("tippt");
      }, 5200);
    }
    return () => clearTimeout(t);
  }, [ruhig, schritt, getippt, zeilen, schluss]);

  const gesendet = schritt !== "tippt";
  const antwortet = schritt === "schreibt" || schritt === "steht";

  return (
    <div className="vf" aria-hidden="true" key={runde}>
      <div className="vf-fensterkopf">
        <i /><i /><i />
        <span>xera-app.com/app/chat</span>
      </div>
      <div className="vf-koerper">
        <div className="vf-leiste">
          <Marke groesse={18} />
          <span className="vf-leiste-zeiger" />
          <Zeichen name="chat" groesse={14} />
          <Zeichen name="cowork" groesse={14} />
          <Zeichen name="code" groesse={14} />
          <Zeichen name="homelab" groesse={14} />
        </div>
        <div className="vf-verlauf">
          <span className="vf-marke">CHAT</span>
          {VERLAUF.map((v, i) => (
            <span key={v} className={"vf-eintrag" + (i === 0 ? " ist-aktiv" : "")} style={{ "--i": i } as React.CSSProperties}>
              {v}
            </span>
          ))}
        </div>
        <div className="vf-haupt">
          <div className="vf-lauf">
            {gesendet && <div className="vf-frage">{FRAGE}</div>}

            {schritt === "denkt" && (
              <p className="status denkt">
                <span className="denkt-kugel" />
                <span className="denkt-wort">denkt nach</span>
              </p>
            )}

            {antwortet && (
              <div className="vf-antwort">
                <strong className="vf-titel">TCP vs. UDP</strong>
                <table>
                  <thead>
                    <tr>
                      <th />
                      <th>TCP</th>
                      <th>UDP</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ZEILEN.slice(0, zeilen).map(([a, b, c]) => (
                      <tr key={a}>
                        <td>{a}</td>
                        <td>{b}</td>
                        <td>{c}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {schluss > 0 && (
                  <p>
                    {SCHLUSS.slice(0, schluss)}
                    {schritt === "schreibt" && <span className="vf-marke-strich" />}
                  </p>
                )}
              </div>
            )}
          </div>

          <div className={"vf-eingabe" + (schritt === "tippt" ? " tippt" : "") + (schritt === "denkt" || schritt === "schreibt" ? " laeuft" : "")}>
            <span>
              {schritt === "tippt" ? FRAGE.slice(0, getippt) : <em>Frag etwas.</em>}
              {schritt === "tippt" && <span className="vf-marke-strich" />}
            </span>
            <span className={"vf-senden" + (schritt === "tippt" && getippt === FRAGE.length ? " drueckt" : "")}>
              <Zeichen name={schritt === "denkt" || schritt === "schreibt" ? "stop" : "senden"} groesse={13} />
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
