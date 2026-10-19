// Eine HTML-Datei headless laden und Laufzeitfehler sammeln (seit 2026-10-16).
//
// Läuft im Sandkasten (arbeitsbereich.py: eigene Kennung, KEIN Netz). Externe
// Skripte (CDN) laden darum nicht — Laufzeitfehler, die davon kommen können,
// meldet das Skript nicht als Fehler, nur Syntaxfehler. Ausgabe: eine
// JSON-Zeile {fehler: [{text, zeile, spalte}], extern_fehlt, info}.
//
// Aufruf: node html_pruefen.cjs /pfad/zur/seite.html
const { chromium } = require("playwright");

const datei = process.argv[2];
const ergebnis = { fehler: [], extern_fehlt: [], info: {} };
const gesehen = new Set();

function merken(text, stack, ausStack = false) {
  // Datei + Zeile aus dem Stack: Fehler können auch in einer eingebundenen .js-Datei liegen (seit 2026-10-17).
  // Playwright zählt Zeilen eingebundener .js-Dateien im Stack ab 0, Skripte im HTML ab 1 (gemessen).
  const m = /([\w.\-]+\.(?:html?|m?js)):(\d+):(\d+)/.exec(stack || "");
  const zeile = m ? Number(m[2]) + (ausStack && /\.m?js$/.test(m[1]) ? 1 : 0) : null;
  const schluessel = text + "|" + zeile;
  if (gesehen.has(schluessel) || ergebnis.fehler.length >= 8) return;
  gesehen.add(schluessel);
  ergebnis.fehler.push({ text: String(text).slice(0, 300), zeile, spalte: m ? Number(m[3]) : null, datei: m ? m[1] : null });
}

(async () => {
  const browser = await chromium.launch({ args: ["--disable-gpu", "--mute-audio", "--autoplay-policy=no-user-gesture-required"] });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  const seite = await ctx.newPage();
  seite.on("pageerror", (e) => merken(e && e.message ? e.message : String(e), e && e.stack, true));
  seite.on("console", (m) => {
    if (m.type() !== "error") return;
    const t = m.text();
    if (/favicon|net::ERR_|Failed to load resource|ERR_NAME|ERR_INTERNET|ERR_NETWORK|Failed to fetch|NetworkError/i.test(t)) return;
    const ort = m.location();
    const quelle = ort && ort.url ? decodeURIComponent(ort.url.split("/").pop() || "") : "";
    const name = /\.(html?|m?js)$/.test(quelle) ? quelle : "x.html";
    merken(t, ort && ort.lineNumber != null ? `${name}:${ort.lineNumber + 1}:${(ort.columnNumber || 0) + 1}` : "");
  });
  seite.on("requestfailed", (r) => {
    const u = r.url();
    // Lokale Datei fehlt (z. B. <script src="spiel.js">, die Datei liegt nicht daneben): dann läuft
    // die Seite gar nicht — vorher meldete der Test trotzdem „keine Fehler“ (2026-10-17).
    if (u.startsWith("file:") && !/favicon/.test(u)) merken("Datei fehlt neben der Seite: " + decodeURIComponent(u.split("/").pop()), "");
    if (!u.startsWith("file:") && !u.startsWith("data:") && !/favicon/.test(u)) ergebnis.extern_fehlt.push(u.slice(0, 160));
  });
  try {
    await seite.goto("file://" + datei, { waitUntil: "load", timeout: 15000 });
  } catch (e) {
    merken("Seite lädt nicht: " + String(e.message || e).slice(0, 200), "");
  }
  await seite.waitForTimeout(1500);
  // Spiele und Apps starten oft erst auf Klick oder Taste — ein paar typische
  // Eingaben, damit auch der Code dahinter einmal läuft.
  try {
    await seite.mouse.click(640, 360);
    await seite.waitForTimeout(300);
    for (const k of ["Enter", "Space", "ArrowRight", "ArrowLeft", "ArrowUp", "ArrowDown", "KeyW", "KeyA", "KeyD", "KeyS"]) {
      await seite.keyboard.down(k);
      await seite.waitForTimeout(120);
      await seite.keyboard.up(k);
    }
    await seite.keyboard.down("ArrowRight");
    await seite.waitForTimeout(1500);
    await seite.keyboard.up("ArrowRight");
    await seite.keyboard.press("Space");
    await seite.waitForTimeout(1000);
    const knopf = await seite.$("button:visible");
    if (knopf) {
      await knopf.click({ timeout: 1000 }).catch(() => {});
      await seite.waitForTimeout(800);
    }
  } catch (e) {
    // Eingaben sind nur ein Zusatz.
  }
  try {
    ergebnis.info = await seite.evaluate(() => ({
      elemente: document.querySelectorAll("*").length,
      text: document.body ? document.body.innerText.trim().length : 0,
      canvas: document.querySelectorAll("canvas").length,
      titel: document.title || "",
    }));
  } catch (e) {
    ergebnis.info = {};
  }
  await browser.close();
  process.stdout.write(JSON.stringify(ergebnis));
})().catch((e) => {
  process.stdout.write(JSON.stringify({ fehler: [{ text: "Prüfung abgebrochen: " + String(e.message || e).slice(0, 200), zeile: null }], abbruch: true }));
});
