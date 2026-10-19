/** Der Rahmen: Leiste, Bereich, Palette, Tastatur. */

import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { Begruessung } from "./bausteine/Begruessung";
import { UpdateHinweis } from "./bausteine/UpdateHinweis";
import { Cli } from "./bereiche/Cli";
import { Lernen } from "./bereiche/Lernen";
import { Start } from "./bereiche/Start";
import { UeberUns } from "./bereiche/UeberUns";
import { Kopfleiste, type Seite } from "./rahmen/Kopfleiste";
import { api } from "./daten/api";
import { QUELLTEXT, SYSTEM } from "./daten/system";
import type { BereichsId, Nutzer, Sitzung } from "./daten/typen";
import { Einstellungen } from "./rahmen/Einstellungen";
import { bereichNach, sichtbareBereiche } from "./rahmen/bereiche";
import { Leiste } from "./rahmen/Leiste";
import { Palette, type Befehl } from "./rahmen/Palette";
import { useThema } from "./stil/useThema";
import "./App.css";

// Der Arbeitsbereich zieht Markdown, Formeln (KaTeX) und Code-Hervorhebung
// nach sich — zusammen mehr als die Hälfte der Anwendung. Die öffentlichen
// Seiten brauchen nichts davon, also wird er erst nach der Anmeldung geladen.
const Gespraechsbereich = lazy(() =>
  import("./bereiche/Gespraechsbereich").then((m) => ({ default: m.Gespraechsbereich })),
);
const Cowork = lazy(() => import("./bereiche/Cowork").then((m) => ({ default: m.Cowork })));

/** Welcher Bereich beim Laden gilt. Aus der Adresse, damit ein Lesezeichen
 *  auf „Homelab" auch dort landet. */
function seiteAusAdresse(): Seite {
  const teil = window.location.pathname.replace(/^\/app\/?/, "");
  return teil === "wie" || teil === "cli" || teil === "ueber" ? teil : "start";
}

/** Angemeldet: /app/start, /app/wie, /app/cli und /app/ueber zeigen die
 *  öffentlichen Seiten statt des Arbeitsbereichs — sonst gäbe es für
 *  Angemeldete keinen Weg mehr dorthin. */
function schaufensterAusAdresse(): boolean {
  const teil = window.location.pathname.replace(/^\/app\/?/, "");
  return teil === "start" || teil === "wie" || teil === "cli" || teil === "ueber";
}

function bereichAusAdresse(): BereichsId {
  const teil = window.location.pathname.replace(/^\/app\/?/, "").split("/")[0];
  return bereichNach(teil).id;
}

/** Fuss der öffentlichen Seiten. Impressum und Datenschutz sind eigene,
 *  statische Seiten auf CT 204 — sie müssen auch im Wartungsmodus für alle
 *  erreichbar sein, wenn die App selbst gesperrt ist. */
function Seitenfuss() {
  return (
    <footer className="seitenfuss">
      <span>Xera AI · ein Projekt aus der Schweiz</span>
      <a href={QUELLTEXT} target="_blank" rel="noopener noreferrer">
        Quelltext auf GitHub
      </a>
      <a href="/impressum">Impressum</a>
      <a href="/datenschutz">Datenschutz</a>
    </footer>
  );
}

export function App() {
  const [nutzer, setNutzer] = useState<Nutzer | null>(null);
  const [ladend, setLadend] = useState(true);
  const [aktiv, setAktiv] = useState<BereichsId>(bereichAusAdresse);
  // 1 = der neue Bereich liegt in der Leiste weiter unten, -1 = weiter oben.
  // Der Inhalt kommt aus dieser Richtung herein (bewegung.css).
  const [richtung, setRichtung] = useState(1);
  const [paletteOffen, setPaletteOffen] = useState(false);
  const [einstellungenOffen, setEinstellungenOffen] = useState(false);
  // Leistenbreite bleibt gespeichert. localStorage kann fehlen (privates
  // Fenster) — dann gilt schmal.
  const [breit, setBreit] = useState(() => {
    try {
      return localStorage.getItem("xera-leiste-breit") === "1";
    } catch {
      return false;
    }
  });
  const breiteUmschalten = useCallback(() => {
    setBreit((b) => {
      try {
        localStorage.setItem("xera-leiste-breit", b ? "0" : "1");
      } catch {
        /* ohne Speicher eben nur für diese Sitzung */
      }
      return !b;
    });
  }, []);
  // Alle Gespräche, für die Suche in der Befehlspalette.
  const [alleGespraeche, setAlleGespraeche] = useState<Sitzung[]>([]);
  const [oeffnen, setOeffnen] = useState<{ id: number; n: number } | null>(null);
  const { thema, umschalten } = useThema();
  // Welche oeffentliche Seite gezeigt wird, solange niemand angemeldet ist.
  const [seite, setSeite] = useState<Seite>(seiteAusAdresse);
  const [schaufenster, setSchaufenster] = useState(schaufensterAusAdresse);

  const zeigeSeite = useCallback(
    (s: Seite) => {
      setSeite(s);
      setSchaufenster(true);
      const angemeldet = Boolean(nutzer && !nutzer.is_guest);
      window.history.pushState(null, "", "/app" + (s === "start" ? (angemeldet ? "/start" : "") : "/" + s));
      window.scrollTo(0, 0);
    },
    [nutzer],
  );

  useEffect(() => {
    api
      .ich()
      .then(setNutzer)
      .catch(() => setNutzer(null))
      .finally(() => setLadend(false));
  }, []);

  const bereiche = useMemo(
    () => sichtbareBereiche(Boolean(nutzer?.has_homelab || nutzer?.is_admin)),
    [nutzer],
  );

  const wechseln = useCallback(
    (id: BereichsId) => {
      // Wer die Rolle verliert, während er im Homelab steht, landet im Chat
      // statt in einem Bereich, der ihm nichts liefert.
      const erlaubt = bereiche.some((b) => b.id === id) ? id : "chat";
      // Ein offener Auftrag „Gespräch öffnen“ gilt nur für diesen Wechsel —
      // sonst öffnet sich das Gespräch bei jeder Rückkehr in den Bereich neu.
      setOeffnen(null);
      setSchaufenster(false);
      const von = bereiche.findIndex((b) => b.id === aktiv);
      const nach = bereiche.findIndex((b) => b.id === erlaubt);
      if (nach !== von) setRichtung(nach > von ? 1 : -1);
      setAktiv(erlaubt);
      window.history.pushState(null, "", `/app/${erlaubt}`);
    },
    [bereiche, aktiv],
  );

  // Zurück-Taste des Browsers.
  useEffect(() => {
    const auf = () => {
      setAktiv(bereichAusAdresse());
      setSeite(seiteAusAdresse());
      setSchaufenster(schaufensterAusAdresse());
    };
    window.addEventListener("popstate", auf);
    return () => window.removeEventListener("popstate", auf);
  }, []);

  // Beim Öffnen der Palette die Gespräche aller Bereiche holen.
  useEffect(() => {
    if (!paletteOffen || !nutzer || nutzer.is_guest) return;
    api.sitzungen().then(setAlleGespraeche).catch(() => {});
  }, [paletteOffen, nutzer]);

  const befehle = useMemo<Befehl[]>(() => {
    const liste: Befehl[] = bereiche.map((b) => ({
      id: "gehe-" + b.id,
      name: `${b.name} — ${b.kurz}`,
      stichworte: b.id,
      gruppe: "Wechseln",
      zeichen: b.id,
      taste: `Strg ${b.taste}`,
      ausfuehren: () => wechseln(b.id),
    }));

    for (const [s, name] of [
      ["start", "Startseite ansehen"],
      ["wie", "How Xera works — der Lernteil"],
      ["cli", "CLI — Xera im Terminal"],
      ["ueber", "Über uns"],
    ] as const) {
      liste.push({
        id: "seite-" + s,
        name,
        stichworte: "webseite öffentlich homepage landing",
        gruppe: "Seiten",
        zeichen: "pfeil-rechts",
        ausfuehren: () => zeigeSeite(s),
      });
    }

    liste.push({
      id: "agents",
      name: "Agents anzeigen und festlegen",
      stichworte: "agent @ werkzeuge spezialist",
      gruppe: "Ansicht",
      zeichen: "agent",
      ausfuehren: () => window.dispatchEvent(new Event("xera:agents")),
    });

    liste.push({
      id: "leiste",
      name: breit ? "Leiste schmal" : "Leiste breit, mit Beschriftung",
      stichworte: "sidebar seitenleiste beschriftung",
      gruppe: "Ansicht",
      zeichen: "leiste",
      taste: "Strg B",
      ausfuehren: breiteUmschalten,
    });

    liste.push({
      id: "einstellungen",
      name: "Konto, Einstellungen, Tastenkürzel",
      stichworte: "settings konto tasten shortcuts hilfe",
      gruppe: "Ansicht",
      zeichen: "einstellungen",
      taste: "Strg /",
      ausfuehren: () => setEinstellungenOffen(true),
    });

    liste.push({
      id: "thema",
      name: thema === "dark" ? "Helles Aussehen" : "Dunkles Aussehen",
      stichworte: "theme hell dunkel farbe licht",
      gruppe: "Ansicht",
      ausfuehren: umschalten,
    });

    liste.push({
      id: "abmelden",
      name: "Abmelden",
      gruppe: "Konto",
      ausfuehren: () => {
        window.location.href = "/auth/logout";
      },
    });

    // Gespräche aus allen Bereichen. Ein Treffer wechselt in den passenden
    // Bereich und öffnet das Gespräch dort.
    const nachAblage: Record<string, BereichsId> = { chat: "chat", agents: "chat", code: "code", homelab: "homelab" };
    for (const g of alleGespraeche) {
      const ziel = nachAblage[g.mode];
      if (!ziel || !bereiche.some((b) => b.id === ziel)) continue;
      liste.push({
        id: "gespraech-" + g.id,
        name: g.title || "Ohne Titel",
        stichworte: `${g.mode} ${g.folder ?? ""}`,
        gruppe: "Gespräche",
        zeichen: ziel,
        nurBeiSuche: true,
        ausfuehren: () => {
          wechseln(ziel);
          setOeffnen({ id: g.id, n: Date.now() });
        },
      });
    }

    return liste;
  }, [bereiche, wechseln, thema, umschalten, breit, breiteUmschalten, alleGespraeche, zeigeSeite]);

  // Tastenkürzel. Nur wenn nicht gerade getippt wird — sonst schluckt
  // Strg+N im Textfeld die Eingabe.
  useEffect(() => {
    function taste(e: KeyboardEvent) {
      const strg = e.ctrlKey || e.metaKey;
      if (!strg) return;

      if (e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOffen((o) => !o);
        return;
      }
      if (e.key.toLowerCase() === "b" && !e.altKey) {
        e.preventDefault();
        breiteUmschalten();
        return;
      }
      if (e.key === "/") {
        e.preventDefault();
        setEinstellungenOffen((o) => !o);
        return;
      }

      const passt = bereiche.find((b) => b.taste === e.key);
      if (passt) {
        e.preventDefault();
        wechseln(passt.id);
      }
    }
    window.addEventListener("keydown", taste);
    return () => window.removeEventListener("keydown", taste);
  }, [bereiche, wechseln, breiteUmschalten]);

  if (ladend) {
    return (
      <div className="anlauf">
        <span className="anlauf-strich" aria-hidden="true" />
        <span className="nur-vorlesen">Wird geladen</span>
      </div>
    );
  }

  // /api/me liefert nie null: Wer nicht angemeldet ist, bekommt ein
  // Gastobjekt mit is_guest. Ohne diese Prüfung sieht ein Gast die
  // Arbeitsoberfläche und die Startseite niemand.
  if (!nutzer || nutzer.is_guest) {
    const anmelden = () => {
      window.location.href = "/auth/login?next=" + encodeURIComponent(window.location.pathname.startsWith("/app") ? window.location.pathname : "/app");
    };
    return (
      <div className="oeffentlich">
        <Kopfleiste aktiv={seite} aufWechsel={zeigeSeite} aufAnmelden={anmelden} />
        {seite === "wie" ? (
          <Lernen aufZurueck={() => zeigeSeite("start")} />
        ) : seite === "cli" ? (
          <Cli aufSchluessel={anmelden} knopf="Anmelden" angemeldet={false} />
        ) : seite === "ueber" ? (
          <UeberUns />
        ) : (
          <Start aufAnmelden={anmelden} aufWie={() => zeigeSeite("wie")} />
        )}
        <Seitenfuss />
      </div>
    );
  }

  // Angemeldet, aber auf einer öffentlichen Seite: dieselben Seiten, nur
  // führt der Knopf zurück in die App statt zur Anmeldung.
  if (schaufenster) {
    const zurApp = () => wechseln(aktiv);
    // „Schlüssel holen“ auf der Seite CLI: zurück in die App, Einstellungen offen.
    const zumSchluessel = () => {
      wechseln(aktiv);
      setEinstellungenOffen(true);
    };
    return (
      <div className="oeffentlich">
        <Kopfleiste aktiv={seite} aufWechsel={zeigeSeite} aufAnmelden={zurApp} knopf="Zur App →" />
        {seite === "wie" ? (
          <Lernen aufZurueck={() => zeigeSeite("start")} />
        ) : seite === "cli" ? (
          <Cli aufSchluessel={zumSchluessel} knopf="Schlüssel holen" angemeldet />
        ) : seite === "ueber" ? (
          <UeberUns />
        ) : (
          <Start aufAnmelden={zurApp} aufWie={() => zeigeSeite("wie")} knopf="Zur App" />
        )}
        <Seitenfuss />
      </div>
    );
  }

  return (
    <div className="rahmen" style={{ "--richtung": richtung } as React.CSSProperties}>
      <Leiste
        bereiche={bereiche}
        aktiv={aktiv}
        aufWechsel={wechseln}
        nutzer={nutzer}
        aufPalette={() => setPaletteOffen(true)}
        breit={breit}
        aufBreite={breiteUmschalten}
        aufEinstellungen={() => setEinstellungenOffen(true)}
        aufStartseite={() => zeigeSeite("start")}
      />

      <UpdateHinweis />

      <Suspense fallback={<main className="haupt"><div className="anlauf"><span className="anlauf-strich" aria-hidden="true" /></div></main>}>
      {aktiv === "cowork" ? (
        <Cowork key="cowork" />
      ) : (
        <Gespraechsbereich
          key={aktiv}
          bereich={bereichNach(aktiv)}
          oeffnen={oeffnen}
          platzhalter={
            aktiv === "homelab"
              ? "Was soll ich auf dem Server nachsehen?"
              : aktiv === "code"
                ? "Code, Fehler, Umbau…"
                : "Frag etwas."
          }
          begruessung={(fragen) =>
            aktiv === "homelab" ? (
              <Begruessung
                zeichen="homelab"
                titel="Homelab"
                text="Zugriff auf Server, Container und Netz. Alles, was etwas verändert, fragt vorher nach — die Argumente stehen dann offen da."
                warnung="Werkzeuge greifen auf echte Systeme zu. Was du hier freigibst, passiert wirklich."
                vorschlaege={[
                  "Wie geht es den Proxmox-Nodes gerade?",
                  "Welche Container laufen auf Node 2?",
                  "Zeig mir die letzten Warnungen aus Grafana.",
                ].map((t) => ({ text: t, aufKlick: () => fragen(t) }))}
              />
            ) : aktiv === "code" ? (
              <Begruessung
                zeichen="code"
                titel="Code"
                text="Schreiben, prüfen, umbauen, Fehler suchen. Dateien bleiben im Arbeitsordner dieses Gesprächs, Webseiten und Spiele testet Xera im Browser. Sag dazu, welche Sprache und welche Version — das entscheidet bei den meisten Fragen die Antwort."
                vorschlaege={[
                  "Schreib ein Python-Skript, das doppelte Dateien in einem Ordner findet.",
                  "Erklär mir den Unterschied zwischen async und Threads in Python.",
                  "Bau mir eine Bash-Funktion, die ein Backup mit Datum anlegt.",
                ].map((t) => ({ text: t, aufKlick: () => fragen(t) }))}
              />
            ) : (
              <Begruessung
                zeichen="chat"
                titel="Chat"
                text={`Fragen, Recherche, Dokumente lesen. Läuft auf ${SYSTEM.modell} auf eigener Hardware in der Schweiz — deine Fragen gehen an kein fremdes KI-Unternehmen.`}
                vorschlaege={[
                  "Erklär mir den Unterschied zwischen TCP und UDP, mit einer Tabelle.",
                  "Fass mir die wichtigsten Punkte zu VLANs in fünf Sätzen zusammen.",
                  "Hilf mir, eine höfliche Absage für ein Meeting zu schreiben.",
                ].map((t) => ({ text: t, aufKlick: () => fragen(t) }))}
              />
            )
          }
        />
      )}

      </Suspense>

      <Einstellungen
        offen={einstellungenOffen}
        aufSchliessen={() => setEinstellungenOffen(false)}
        nutzer={nutzer}
        thema={thema}
        aufThema={umschalten}
        breit={breit}
        aufBreite={breiteUmschalten}
      />

      <Palette
        offen={paletteOffen}
        aufSchliessen={() => setPaletteOffen(false)}
        befehle={befehle}
      />
    </div>
  );
}
