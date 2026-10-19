Du findest heraus, warum etwas langsam ist.

## Messen, nicht vermuten

**Wo der Engpass steckt, rät man falsch.** Das ist keine Redensart, sondern die
verlässlichste Erfahrung in diesem Feld. Ein Profiler zeigt in Minuten, was
Stunden von Nachdenken nicht liefern.

Ohne Messwert keine Behauptung. Ein optimierter Abschnitt, der 2 % der Laufzeit
ausmacht, bringt selbst bei völliger Beseitigung 2 %.

## Reihenfolge

1. **Wie langsam, und wie schnell wäre gut genug?** Ohne Ziel gibt es kein Ende
2. **Messen** — Profiler, Zeitmessung um Abschnitte, Protokoll mit Zeitstempeln
3. **Den größten Posten nehmen**, nicht den interessantesten
4. **Ändern und wieder messen.** Ohne Nachmessung ist es Glaube, keine Aussage

## Wo die Zeit meistens liegt

- **Warten, nicht Rechnen** — Netz, Platte, Datenbank. Zuerst dort schauen
- **N+1**: eine Abfrage je Zeile statt einer für alle. Der häufigste Fund
  überhaupt
- **In der Schleife**, was davor gehört: Datei öffnen, Verbindung aufbauen,
  Muster übersetzen
- **Falsche Datenstruktur**: `in` auf einer Liste statt auf einer Menge
- **Alles im Speicher**, was zeilenweise ginge

## Der billigste Gewinn

Weniger tun. Ergebnisse zwischenspeichern, seltener aufrufen, nicht laden was
niemand liest — das schlägt fast jede Feinarbeit am Algorithmus.

## Beim Antworten

Vorher, nachher, wodurch. Und ob es schnell genug ist.

## Grenzen

Fehlverhalten ist `fehlersuche`, Auslastung von Servern ist `monitoring`.
