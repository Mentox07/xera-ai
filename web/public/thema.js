// Hell oder dunkel vor dem ersten Malen setzen, sonst blitzt beim Laden kurz das falsche
// Aussehen auf. Eigene Datei statt Inline-Skript (bis 2026-10-19 in index.html): So muss die
// Content-Security-Policy in Caddy keine Inline-Skripte erlauben.
try {
  var w = localStorage.getItem("xera-theme");
  document.documentElement.dataset.theme =
    w === "light" || w === "dark"
      ? w
      : matchMedia("(prefers-color-scheme: light)").matches
        ? "light"
        : "dark";
} catch (e) {
  document.documentElement.dataset.theme = "dark";
}
