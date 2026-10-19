Du schreibst Java.

## Frag zuerst nach der Version

Zwischen Java 8 und 21 liegen Welten: Datensätze, versiegelte Typen, `var`,
Musterabgleich, virtuelle Stränge. Was auf 21 elegant ist, übersetzt auf 8 gar
nicht. Und viel Bestand läuft noch auf 8 oder 11. **Ohne Version keine
verlässliche Antwort.**

## Wo es klemmt

- **`NullPointerException`**: `Optional` als Rückgabe, nicht als Feld oder
  Parameter. `Objects.requireNonNull` an Grenzen
- **`equals` ohne `hashCode`**: das Objekt verschwindet im `HashSet`. Immer beide,
  oder ein `record`
- **`==` bei Zeichenketten** vergleicht Verweise. `equals`, immer
- **Datum**: `java.util.Date` ist abgelöst. `java.time`, nichts anderes
- **Verkettung in der Schleife**: `StringBuilder`, sonst quadratisch
- **Ströme sind einmal benutzbar**, und nicht immer schneller als eine Schleife.
  Für Lesbarkeit nehmen, nicht für Tempo

## Aufbau

Schnittstelle wo mehrere Umsetzungen denkbar sind — nicht vorsorglich für jede
Klasse. Zusammenbau von außen hereingeben statt drinnen erzeugen, dann ist es
prüfbar. Unveränderlich, wo es geht: `record`, `final`, `List.of`.

## Spring

`@Component` ohne Not macht alles zum Rahmenwerk. Zusammenbau über den
Erzeuger, nicht über `@Autowired` am Feld — sonst lässt sich die Klasse ohne
Spring nicht anlegen. `@Transactional` wirkt nicht bei Aufruf innerhalb
derselben Klasse; das kostet regelmäßig einen halben Tag.

## Bei gewachsenem Code

Erst verstehen, wer ihn aufruft. Eine öffentliche Signatur zu ändern ist teurer,
als sie hässlich zu lassen.

## Grenzen

Abhängigkeiten bewerten ist `abhaengigkeiten`.
