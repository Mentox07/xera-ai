/** Was auf einer leeren Fläche steht.
 *
 * Nicht „Wie kann ich dir heute helfen?" — die Frage stellt niemand, der schon
 * hier ist, und sie sagt nichts über den Bereich. Stattdessen: was dieser
 * Bereich kann, und drei Anfänge zum Antippen.
 */

import { Zeichen, type ZeichenName } from "./Zeichen";
import "./Begruessung.css";

interface Eigenschaften {
  zeichen: ZeichenName;
  titel: string;
  text: string;
  vorschlaege?: { text: string; aufKlick: () => void }[];
  warnung?: string;
}

export function Begruessung({ zeichen, titel, text, vorschlaege, warnung }: Eigenschaften) {
  return (
    <div className="begruessung">
      <span className="begruessung-zeichen" aria-hidden="true">
        <Zeichen name={zeichen} groesse={22} />
      </span>
      <h2>{titel}</h2>
      <p className="begruessung-text">{text}</p>

      {warnung && (
        <p className="begruessung-warnung">
          <Zeichen name="warnung" groesse={14} />
          {warnung}
        </p>
      )}

      {vorschlaege && vorschlaege.length > 0 && (
        <ul className="begruessung-vorschlaege">
          {vorschlaege.map((v, i) => (
            <li key={v.text} style={{ "--i": i } as React.CSSProperties}>
              <button type="button" onClick={v.aufKlick}>
                <Zeichen name="pfeil-rechts" groesse={13} />
                {v.text}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
