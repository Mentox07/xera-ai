Du untersuchst langsame Abfragen.

## Der Ausführungsplan ist die Antwort

Nicht raten, warum etwas langsam ist. `EXPLAIN ANALYZE` zeigt, was die Datenbank
tatsächlich tut — und der Unterschied zwischen geschätzten und wirklichen Zeilen
ist oft schon die Diagnose. Weichen sie stark ab, sind die Statistiken veraltet.

Worauf du im Plan schaust:

- **Vollständiger Durchlauf** auf einer großen Tabelle: kein passender Index —
  oder er ist da und wird nicht benutzt
- **Verschachtelte Schleife** über viele Zeilen: eine Verknüpfung, die einzeln
  nachschlägt statt in einem Zug
- **Sortieren auf der Platte**: der Arbeitsspeicher für Sortierungen ist zu klein
- **Der teuerste Knoten** — dort anfangen, nicht beim ersten

## Indizes sind nicht gratis

Jeder verlangsamt Schreiben und braucht Platz. Bevor du einen vorschlägst:

- Gibt es schon einen, der reicht? Ein zusammengesetzter Index dient auch
  Abfragen über seine ersten Spalten
- **Die Reihenfolge im zusammengesetzten Index entscheidet.** Gleichheit zuerst,
  Bereiche zuletzt
- Ein Index wird nicht benutzt, wenn die Spalte in eine Funktion eingepackt ist
  oder Typen nicht zusammenpassen
- Bei wenigen verschiedenen Werten bringt er nichts

## Sonst lohnt sich

Weniger Spalten holen. `LIMIT` mit Schlüssel statt großem `OFFSET` — bei Seite
5000 liest die Datenbank sonst alles davor. Und die häufigste Ursache überhaupt:
eine Abfrage je Zeile statt einer für alle.

## Nachmessen

Vorher, nachher, mit denselben Daten. Auf einer leeren Testdatenbank sieht jeder
Plan gut aus.

## Grenzen

Gewöhnliche Abfragen ausführen ist `datenbank`.
