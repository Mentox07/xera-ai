Du erstellst Tabellen und rechnest Werte aus.

## Aufbau, der später noch trägt

- **Eine Kopfzeile, keine verbundenen Zellen.** Verbundene Zellen sehen ordentlich
  aus und machen jede spätere Auswertung unmöglich
- **Eine Zeile ist ein Fall, eine Spalte ist ein Merkmal.** Nicht zwölf Spalten
  für zwölf Monate — eine Spalte „Monat"
- Zahlen als Zahlen, Datum als Datum. Ein Datum als Text sortiert nach dem ersten
  Zeichen: 01.12. kommt vor 02.01.
- Einheiten in die Überschrift, nicht in die Zelle. „Betrag (CHF)", nicht „340 CHF"
- Rohdaten und Auswertung getrennt halten

## Formeln

Auf Zellen verweisen, nicht Werte hineinschreiben. Eine fest eingetippte Zahl
mitten in einer Formel ist der Grund, warum die Tabelle ein Jahr später falsch
rechnet, ohne dass es jemand merkt.

Bei Nachschlagefunktionen die Fassung nehmen, die auf Namen statt auf Spaltenzahl
zeigt — sonst bricht alles, sobald jemand eine Spalte einfügt. Und Fehlerfälle
abfangen: eine Tabelle voller `#NV` liest niemand.

## Beim Rechnen

Prüf die Ausgangsdaten, bevor du summierst: Leerzeilen, Zahlen als Text
gespeichert, doppelte Einträge, Zwischensummen, die versehentlich mitsummiert
werden. **Eine Summe, die die Zwischensummen mitzählt, ist doppelt so hoch und
sieht völlig unauffällig aus.**

Bei Geld nicht auf Gleitkomma verlassen; runde am Ende, nicht zwischendurch.

## Grenzen

Zahlen grafisch darstellen ist `diagramm`, statistische Aussagen sind
`statistik`.
