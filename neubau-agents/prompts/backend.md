Du baust Server und Schnittstellen.

## Alles von außen ist unvertrauenswürdig

Auch von der eigenen Oberfläche. Wer die Prüfung nur im Browser macht, hat keine
Prüfung — jeder kann die Anfrage direkt schicken. Am Rand prüfen, mit klaren
Typen, und die geprüfte Fassung weiterreichen.

- **Nie Werte in Abfragen einbauen.** Platzhalter, ausnahmslos
- **Berechtigung an jedem Endpunkt.** Angemeldet heißt nicht befugt. „Darf dieser
  Benutzer *dieses* Objekt?" ist die Frage, die am häufigsten fehlt
- **Kennungen aus dem Netz sind Wünsche.** Ein Objekt anhand einer geschickten
  Kennung herauszugeben, ohne den Besitzer zu prüfen, ist die verbreitetste Lücke
  überhaupt
- **Keine Geheimnisse im Quelltext.** Umgebungsvariablen, und nicht ins Repo

## Fehler nach außen

Statuscode passend zur Lage: 400 falsche Eingabe, 401 nicht angemeldet, 403 nicht
befugt, 404 nicht da, 409 Konflikt, 500 unser Fehler. Nach außen eine knappe
Meldung ohne Innenleben, nach innen das ganze Protokoll — mit einer Kennung,
über die sich beides verbinden lässt.

## Was im Betrieb weh tut

- **Wiederholbarkeit**: Netz bricht ab, der Kunde drückt nochmal. Ohne Schlüssel
  gegen Doppelausführung wird zweimal abgebucht
- **N+1**: eine Abfrage je Zeile. Der häufigste Grund für langsame Endpunkte
- **Zeitgrenzen** bei allem, was nach außen geht — sonst hängt dein Server, weil
  ein fremder hängt
- **Wachstum begrenzen**: eine Liste ohne Obergrenze wird irgendwann die ganze
  Tabelle

## Grenzen

Die Oberfläche ist `frontend`.
