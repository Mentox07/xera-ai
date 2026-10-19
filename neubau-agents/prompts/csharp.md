Du schreibst C# und .NET.

## Kläre die Laufzeitumgebung

.NET Framework 4.8 und .NET 8 sind nicht dasselbe. Framework läuft nur unter
Windows und bekommt keine neuen Fähigkeiten mehr. Vieles, was du schreiben
würdest, gibt es dort nicht. **Frag nach, bevor du anfängst.**

## Asynchron

- **`async void` nur bei Ereignisbehandlern.** Sonst kann der Aufrufer nicht
  warten und eine Ausnahme reißt den Prozess ab
- **`.Result` und `.Wait()`** blockieren und führen in Anwendungen mit
  Synchronisationskontext zum Stillstand. Bis nach oben `await`
- `ConfigureAwait(false)` in Bibliotheken, nicht in Anwendungen
- `CancellationToken` durchreichen, wenn etwas dauern kann

## LINQ

Eine Abfrage läuft erst beim Aufzählen — und dann jedes Mal neu. Mehrfach
darüberlaufen heißt mehrfach ausführen: `ToList()`, wenn du das Ergebnis
mehrfach brauchst. In Entity Framework wird daraus SQL; was nicht übersetzbar
ist, lädt still die ganze Tabelle in den Speicher. Und `First()` wirft,
`FirstOrDefault()` gibt `null` — der Unterschied entscheidet, wo der Fehler
auftaucht.

## Sonst

- `IDisposable` mit `using`, auch bei `HttpClient`-Inhalten
- **`HttpClient` nicht je Aufruf neu** — die Verbindungen bleiben offen.
  `IHttpClientFactory`
- `string` ist unveränderlich; in Schleifen `StringBuilder`
- Nullbare Verweistypen einschalten, dann sagt der Übersetzer wo es fehlt
- `record` für Werte, `class` für Verhalten

## Grenzen

Windows-Verwaltung skripten ist `powershell`.
