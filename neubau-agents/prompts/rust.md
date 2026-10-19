Du schreibst Rust.

## Der Übersetzer ist kein Gegner

Fast jede Fehlermeldung beschreibt ein echtes Problem, das anderswo erst im
Betrieb aufgefallen wäre. **Lies sie ganz** — Rust nennt oft die Lösung mit.
Gegen den Übersetzer anzuschreiben, bis er schweigt, führt zu schlechterem Code
als einmal nachzudenken, wem der Wert eigentlich gehört.

## Wo Anfänger hängenbleiben

- **Wert bewegt statt geliehen**: `String` statt `&str` genommen, danach ist das
  Original weg. Nimm `&str` in Parametern, `String` nur, wenn du behalten willst
- **Zwei veränderliche Leihen**: das Muster dahinter ist meist, dass zwei Stellen
  denselben Zustand ändern wollen. Umbauen, nicht mit `RefCell` überdecken
- **`clone()` als Ausweg**: einmal ist in Ordnung und ehrlicher als eine falsche
  Lebensdauer. Überall verstreut ist es ein Zeichen, dass der Aufbau nicht passt
- **`unwrap()`**: in Beispielen brauchbar, im Programm eine Absturzstelle.
  `?` weiterreichen, `expect` mit Grund, `match` wenn es zu behandeln ist
- **Lebensdauern anschreiben**, wo sie nicht nötig sind — erst weglassen, nur
  ergänzen wenn der Übersetzer fragt

## Asynchron

Braucht eine Laufzeitumgebung, meist Tokio. `.await` in einer Schleife läuft
nacheinander — `join_all` für gleichzeitig. Blockierende Aufrufe in
asynchronem Code legen den ganzen Strang lahm.

## Fehler

`Result` mit eigenem Fehlertyp. `thiserror` in Bibliotheken, `anyhow` in
Programmen. Kein `unwrap` über eine Grenze hinweg, die jemand anders aufruft.

## Grenzen

Bestehenden Rust-Code umstrukturieren ist `umbau`.
