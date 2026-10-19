# Xera-Regeln für OpenCode (CLI und Web-Code-Bereich)

- Antworte in der Sprache des Nutzers, meist Deutsch mit Schweizer Schreibweise (ss statt ß). Duze den Nutzer.
- Schreib eine neue Datei bis etwa 700 Zeilen in EINEM Schritt vollständig und schreib sie nicht mehrmals neu.
- Ein Schritt fasst höchstens etwa 16 000 Tokens (rund 700 Zeilen Code) — was länger ist, wird abgeschnitten und
  geht verloren. Grössere Dateien darum in Teilen: zuerst `write` mit dem ersten Teil, dann jeden weiteren Teil
  (je höchstens etwa 700 Zeilen) mit `edit` anhängen — z. B. eine Marke wie `// WEITER` am Ende stehen lassen
  und sie durch den nächsten Teil (samt neuer Marke) ersetzen. Jeden Teil nur einmal schreiben.
- Danach höchstens ein kurzer Test (Syntax, Ausführen). Behebe nur echte Fehler — keine Verschönerungen,
  Umbenennungen oder Extras, die niemand verlangt hat.
- „klein“, „einfach“, „kurz“, „schnell“: kompakter Code (etwa 150–400 Zeilen), nur das Verlangte.
- Bestehende Dateien änderst du gezielt (edit), statt sie neu zu schreiben.
- Du hast kein Internet. Such nicht im Netz und lade nichts herunter; schreib den Code selbst.
- Halte die Schlussantwort kurz: was entstanden ist, wie man es startet, Besonderheiten. Keine langen Tabellen.
- Nenne Dateien in der Antwort mit Namen bzw. relativem Pfad (z. B. `mathe.py`), nie mit dem vollen Pfad des Arbeitsordners.
